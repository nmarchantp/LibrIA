"""Prueba la migración real en un esquema aislado y revierte todo el escenario."""
import importlib
import unittest
import uuid
from unittest.mock import patch

from sqlalchemy import text

from app.core.database import engine
from scripts.seed_demo import stable_id as account_id
from scripts.seed_analytics_demo import stable_id as source_id


class ReviewMigrationTest(unittest.TestCase):
    def test_verified_only_preserves_comments_images_likes_and_provenance(self):
        schema = "test_reviews_" + uuid.uuid4().hex
        with engine.connect() as connection:
            transaction = connection.begin()
            try:
                connection.execute(text(f"CREATE SCHEMA {schema}"))
                tables = ("usuarios", "perfiles", "obras", "ediciones", "fuentes_catalogo", "publicaciones",
                          "imagenes_publicacion", "me_gusta_publicacion", "comentarios_publicacion", "procedencia_demo")
                for table in tables:
                    connection.execute(text(f"CREATE TABLE {schema}.{table} (LIKE app.{table} INCLUDING ALL)"))
                # Restaurar únicamente la estructura de origen anterior a 0016.
                connection.execute(text(f"ALTER TABLE {schema}.publicaciones DROP COLUMN legacy_content CASCADE"))
                connection.execute(text(f"ALTER TABLE {schema}.comentarios_publicacion DROP COLUMN review_id CASCADE"))
                connection.execute(text(f"ALTER TABLE {schema}.comentarios_publicacion ADD CONSTRAINT ck_comentarios_destino CHECK (num_nonnulls(post_id, reading_event_id)=1)"))
                reader, author = account_id("user:lector"), account_id("user:autor")
                reader_profile, author_profile = account_id("profile:lector"), account_id("profile:autor")
                for table, column, ids in (("usuarios", "id", (reader, author)),
                                           ("perfiles", "id", (reader_profile, author_profile)),
                                           ("obras", "id", (source_id("work:journey"), source_id("work:garden"))),
                                           ("ediciones", "id", (source_id("edition:journey:es"), source_id("edition:garden:es"))),
                                           ("fuentes_catalogo", "edition_id", (source_id("edition:journey:es"), source_id("edition:garden:es")))):
                    connection.execute(text(f"INSERT INTO {schema}.{table} SELECT * FROM app.{table} WHERE {column} IN (:a,:b)"), {"a": ids[0], "b": ids[1]})
                cases = ((reader, reader_profile, "analytics-demo:journey:es"),
                         (author, None, "analytics-demo:journey:es"),
                         (author, author_profile, "unmapped:reference"),
                         (author, author_profile, "analytics-demo:garden:es"),
                         (author, author_profile, "analytics-demo:garden:es"),
                         (author, reader_profile, "analytics-demo:garden:es"))
                post_ids = []
                for user, profile, reference in cases:
                    post_id = uuid.uuid4()
                    post_ids.append(post_id)
                    connection.execute(text(f"""INSERT INTO {schema}.publicaciones
                        (id,user_id,author_profile_id,author_role,source,kind,body,book_ref,rating)
                        VALUES (:id,:user,:profile,'lector','review','reviews','Reseña legada',:ref,NULL)"""),
                        {"id": post_id, "user": user, "profile": profile, "ref": reference})
                valid_id, image_id, comment_id = post_ids[0], uuid.uuid4(), uuid.uuid4()
                connection.execute(text(f"INSERT INTO {schema}.imagenes_publicacion (id,post_id,content_type,data) VALUES (:id,:post,'image/png',:data)"),
                                   {"id": image_id, "post": valid_id, "data": b"\x89PNG\r\n\x1a\ntest"})
                connection.execute(text(f"INSERT INTO {schema}.me_gusta_publicacion (post_id,user_id) VALUES (:post,:user)"), {"post": valid_id, "user": author})
                connection.execute(text(f"INSERT INTO {schema}.comentarios_publicacion (id,post_id,user_id,body) VALUES (:id,:post,:user,'Comentario conservado')"),
                                   {"id": comment_id, "post": valid_id, "user": author})
                connection.execute(text(f"INSERT INTO {schema}.procedencia_demo VALUES ('post',:id,'migration-test')"), {"id": valid_id})
                migration = importlib.import_module("migrations.versions.0016_normalized_reviews")

                class IsolatedOperations:
                    def execute(self, sql):
                        connection.execute(text(sql.replace("app.", schema + ".")))

                with patch.object(migration, "op", IsolatedOperations()):
                    migration.upgrade()
                report = dict(connection.execute(text(f"SELECT reason_code, count(*) FROM {schema}.migraciones_resenas GROUP BY reason_code")).all())
                self.assertEqual(report, {"verified": 2, "work_unresolved": 1, "duplicate_profile_work": 2, "profile_unresolved": 1})
                self.assertEqual(connection.execute(text(f"SELECT count(*) FROM {schema}.publicaciones")).scalar_one(), 6)
                self.assertIsNone(connection.execute(text(f"SELECT rating FROM {schema}.resenas WHERE id=:id"), {"id": valid_id}).scalar_one())
                comment = connection.execute(text(f"SELECT post_id,review_id FROM {schema}.comentarios_publicacion WHERE id=:id"), {"id": comment_id}).one()
                self.assertEqual(tuple(comment), (None, valid_id))
                self.assertEqual(connection.execute(text(f"SELECT id FROM {schema}.imagenes_resena WHERE review_id=:id"), {"id": valid_id}).scalar_one(), image_id)
                self.assertEqual(connection.execute(text(f"SELECT user_id FROM {schema}.me_gusta_resena WHERE review_id=:id"), {"id": valid_id}).scalar_one(), author)
                self.assertEqual(connection.execute(text(f"SELECT dataset_version FROM {schema}.procedencia_demo WHERE entity_type='review' AND entity_id=:id"), {"id": valid_id}).scalar_one(), "migration-test")
            finally:
                transaction.rollback()

"""In-place publication edits and non-destructive removal."""
import json
import uuid
from datetime import datetime, timezone
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile
from app.core.database import get_db
from app.modules.auth.dependencies import get_current_user
from app.modules.books.models import Work, Edition, CatalogSource
from app.modules.social.activity_access import resolve_activity
from app.modules.social.models import PostBookCover, PostImage
from app.modules.social.post_covers import require_post_editor, read_cover
from app.modules.social.router import image_content_type, MAX_IMAGE_BYTES, MAX_IMAGES_TOTAL_BYTES, MAX_POST_IMAGES
from app.modules.users.identities import publication_role
from app.modules.users.identity_models import Profile
from app.modules.users.models import User

router=APIRouter(prefix='/posts',tags=['publication management'])
DB=Annotated[Session,Depends(get_db)]
Viewer=Annotated[User,Depends(get_current_user)]


class PublicationEdit(BaseModel):
    model_config=ConfigDict(extra='forbid',str_strip_whitespace=True)
    publication_type: Literal['free','event','promotion','news','launch','institutional','note','theory']
    source: Literal['community','event']
    kind: Literal['community']='community'
    author_profile_id: uuid.UUID | None=None
    title: str | None=Field(default=None,max_length=200)
    body: str=Field(min_length=1,max_length=3000)
    book_ref: str | None=Field(default=None,max_length=200)
    book_title: str | None=Field(default=None,max_length=200)
    work_id: uuid.UUID | None=None
    edition_id: uuid.UUID | None=None
    existing_image_ids: list[uuid.UUID] | None=None
    cover_mode: Literal['keep','catalog','custom']='keep'


def full_item(db,user,post):
    from app.modules.social.feed_service import hydrate
    return hydrate(db,[post],user)[('publication',post.id)]


@router.get('/{post_id}')
def get_publication(post_id:uuid.UUID,db:DB,user:Viewer):
    post,_=resolve_activity(db,'publication',post_id)
    return full_item(db,user,post)


@router.put('/{post_id}')
async def edit_publication(post_id:uuid.UUID,request:Request,db:DB,user:Viewer):
    post=require_post_editor(db,user,post_id)
    uploads=[];cover_upload=None
    try:
        if request.headers.get('content-type','').startswith('multipart/form-data'):
            form=await request.form(max_files=MAX_POST_IMAGES+1,max_fields=len(PublicationEdit.model_fields))
            payload={key:form.get(key) for key in PublicationEdit.model_fields if form.get(key) is not None}
            if 'existing_image_ids' in payload:
                try:payload['existing_image_ids']=json.loads(payload['existing_image_ids'])
                except (ValueError,TypeError):raise HTTPException(422,'La selección de imágenes no es válida') from None
            uploads=form.getlist('images');cover_upload=form.get('book_cover')
        elif request.headers.get('content-type','').startswith('application/json'):
            try:payload=await request.json()
            except ValueError:raise HTTPException(422,'El JSON no es válido') from None
        else:raise HTTPException(415,'Usa JSON o multipart/form-data')
        if not isinstance(payload,dict):raise HTTPException(422,'El contenido debe ser un objeto')
        for key in ('title','book_ref','book_title','work_id','edition_id','author_profile_id'):
            if payload.get(key)=='':payload[key]=None
        try:data=PublicationEdit.model_validate(payload)
        except ValidationError as error:raise HTTPException(422,error.errors(include_context=False)) from error
        if data.author_profile_id and data.author_profile_id!=post.author_profile_id:
            raise HTTPException(403,'No puedes cambiar la autoría de una publicación')
        profile=db.get(Profile,post.author_profile_id) if post.author_profile_id else None
        role='admin' if user.role=='admin' and (not profile or profile.kind=='personal') else publication_role(db,profile) if profile else user.role
        if role=='lector' and not (data.publication_type in ('note','theory') and (data.book_ref or data.work_id)):
            raise HTTPException(403,'Tu perfil no puede publicar este tipo de contenido')
        if (data.publication_type=='event')!=(data.source=='event'):
            raise HTTPException(422,'El tipo no corresponde al contenido')
        images=list(db.scalars(select(PostImage).where(PostImage.post_id==post.id)))
        selected={i.id for i in images} if data.existing_image_ids is None else set(data.existing_image_ids)
        if not selected.issubset({i.id for i in images}):raise HTTPException(422,'Una imagen no pertenece a esta publicación')
        if len(selected)+len(uploads)>MAX_POST_IMAGES:raise HTTPException(422,'Puedes conservar hasta 10 fotografías')
        new_images=[]
        total=sum(len(image.data) for image in images if image.id in selected)
        for upload in uploads:
            if not isinstance(upload,UploadFile):raise HTTPException(422,'Cada imagen debe ser un archivo')
            content=await upload.read(MAX_IMAGE_BYTES+1)
            if len(content)>MAX_IMAGE_BYTES:raise HTTPException(413,'Cada imagen admite hasta 5 MB')
            image_type=image_content_type(content)
            if not image_type:raise HTTPException(415,'Usa JPEG, PNG, GIF o WebP')
            total+=len(content);new_images.append((image_type,content))
        cover_data=await read_cover(cover_upload) if cover_upload is not None else None
        existing_cover=db.get(PostBookCover,post.id)
        total+=len(cover_data[1]) if cover_data else len(existing_cover.data) if existing_cover and data.cover_mode=='keep' else 0
        if total>MAX_IMAGES_TOTAL_BYTES:raise HTTPException(413,'Las imágenes y la portada no pueden superar 25 MB')
        same_book=data.book_ref==post.book_ref and ('work_id' not in data.model_fields_set or data.work_id==post.work_id) and ('edition_id' not in data.model_fields_set or data.edition_id==post.edition_id)
        if same_book:
            work_id,edition_id=post.work_id,post.edition_id
        else:
            work_id,edition_id=data.work_id,data.edition_id
            if data.book_ref:
                try: internal=uuid.UUID(data.book_ref)
                except ValueError:internal=None
                if internal and db.get(Work,internal):
                    if work_id and work_id!=internal:raise HTTPException(422,'La obra enlazada no corresponde')
                    work_id=internal
                else:
                    matches=list(db.scalars(select(Edition).join(CatalogSource,CatalogSource.edition_id==Edition.id).where(CatalogSource.external_id==data.book_ref)))
                    if len({e.work_id for e in matches})!=1:raise HTTPException(422,'Selecciona una obra inequívoca del catálogo')
                    if work_id and work_id!=matches[0].work_id:raise HTTPException(422,'La obra enlazada no corresponde')
                    work_id,edition_id=matches[0].work_id,edition_id or matches[0].id
            if work_id and not db.get(Work,work_id):raise HTTPException(422,'Obra no encontrada')
            if edition_id:
                edition=db.get(Edition,edition_id)
                if not edition or edition.work_id!=work_id:raise HTTPException(422,'La edición no corresponde a la obra')
        if cover_data and not (work_id or data.book_ref):raise HTTPException(422,'Enlaza una obra antes de elegir portada')
        if data.cover_mode=='custom' and not cover_data and not existing_cover:
            raise HTTPException(422,'Selecciona una imagen para la portada personalizada')
        post.title,post.body,post.source,post.publication_type=data.title,data.body,data.source,data.publication_type
        post.author_role=role
        post.book_ref,post.book_title,post.work_id,post.edition_id=data.book_ref,data.book_title,work_id,edition_id
        post.updated_at=datetime.now(timezone.utc)
        for image in images:
            if image.id not in selected:db.delete(image)
        db.add_all(PostImage(post_id=post.id,content_type=kind,data=content) for kind,content in new_images)
        if cover_data:
            if not existing_cover:existing_cover=PostBookCover(post_id=post.id);db.add(existing_cover)
            existing_cover.revision,existing_cover.content_type,existing_cover.data=uuid.uuid4(),cover_data[0],cover_data[1]
        elif existing_cover and (data.cover_mode=='catalog' or not same_book or not (work_id or data.book_ref)):
            db.delete(existing_cover)
        db.flush();result=full_item(db,user,post);db.commit()
        return result
    finally:
        for upload in [*uploads,cover_upload]:
            if isinstance(upload,UploadFile):await upload.close()


@router.delete('/{post_id}',status_code=204)
def delete_publication(post_id:uuid.UUID,db:DB,user:Viewer):
    post=require_post_editor(db,user,post_id)
    post.deleted_at=post.updated_at=datetime.now(timezone.utc)
    db.commit()
    return Response(status_code=204)

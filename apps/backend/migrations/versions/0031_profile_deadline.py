"""Bound profile requests including queue wait; preserve deadline on coalescing."""
from alembic import op
revision='0031_profile_deadline'
down_revision='0030_adaptive_reader_ai'
branch_labels=None
depends_on=None


def upgrade():
    op.execute("""ALTER TABLE ia.jobs ADD COLUMN deadline_at timestamptz;
        UPDATE ia.jobs SET deadline_at=LEAST(now()+interval '55 seconds',updated_at+interval '55 seconds')
            WHERE target='profile' AND status IN ('pending','processing');
        CREATE OR REPLACE FUNCTION ia.enqueue(p_owner uuid,p_target text) RETURNS void LANGUAGE plpgsql AS $$
        BEGIN
          INSERT INTO ia.jobs(owner_id,target,not_before,deadline_at)
            VALUES(p_owner,p_target,now()+interval '1 second',CASE WHEN p_target='profile' THEN now()+interval '55 seconds' END)
          ON CONFLICT(owner_id,target) DO UPDATE SET
            revision=ia.jobs.revision+1,
            status=CASE WHEN ia.jobs.status='processing' THEN 'processing' ELSE 'pending' END,
            attempts=CASE WHEN ia.jobs.status='processing' THEN ia.jobs.attempts ELSE 0 END,
            not_before=now()+interval '1 second',updated_at=now(),error_code=NULL,
            deadline_at=CASE WHEN p_target='profile' THEN
              CASE WHEN ia.jobs.status IN ('pending','processing') THEN COALESCE(ia.jobs.deadline_at,now()+interval '55 seconds')
                   ELSE now()+interval '55 seconds' END END;
        END $$;""")


def downgrade():
    raise RuntimeError('Profile request deadlines must be preserved')

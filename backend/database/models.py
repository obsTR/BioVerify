from datetime import datetime
from sqlalchemy import Column, String, Enum, DateTime, JSON, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.dialects.postgresql import UUID
import uuid

Base = declarative_base()


class AnalysisStatus:
    QUEUED = 'queued'
    RUNNING = 'running'
    DONE = 'done'
    FAILED = 'failed'


class Analysis(Base):
    __tablename__ = 'analyses'

    analysis_id = Column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid.uuid4()))
    status = Column(Enum(AnalysisStatus.QUEUED, AnalysisStatus.RUNNING, AnalysisStatus.DONE, AnalysisStatus.FAILED,
                         name='analysis_status'), nullable=False, default=AnalysisStatus.QUEUED)
    policy_name = Column(String(255), nullable=True)
    input_uri = Column(String(512), nullable=False)
    evidence_prefix = Column(String(512), nullable=True)
    result_json = Column(JSON, nullable=True)
    error_code = Column(String(100), nullable=True)
    error_message = Column(String(1000), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index('idx_analyses_created_at', 'created_at'),
        Index('idx_analyses_status', 'status'),
    )

    def to_dict(self):
        return {
            'analysis_id': self.analysis_id,
            'status': self.status,
            'policy_name': self.policy_name,
            'input_uri': self.input_uri,
            'evidence_prefix': self.evidence_prefix,
            'result_json': self.result_json,
            'error_code': self.error_code,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'finished_at': self.finished_at.isoformat() if self.finished_at else None,
        }

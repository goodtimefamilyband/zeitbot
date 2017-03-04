# schema.py (zeitlog)

#import sqlalchemy
from sqlalchemy import Column, ForeignKey, Integer, String, Date, Float, Boolean
from app.schema import engine, Base

class ScoreTbl(Base):
    __tablename__ = "scores"
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    owner = Column(String, nullable=False)
    server = Column(String, nullable=False)
    
class ScoreItem(Base):
    __tablename__ = "score_items"
    
    emoji = Column(String, primary_key=True)
    score = Column(Integer, primary_key=True)
    val = Column(Float, nullable=False, default=1.0)
    
class Reaction(Base):
    __tablename__ = "reactions"
    
    shortcut = Column(String, primary_key=True)
    server = Column(String, primary_key=True)
    emoji = Column(String, nullable=False)
            
Base.metadata.create_all(engine)

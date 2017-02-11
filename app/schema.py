# schema.py

#from config import SQLALCHEMY_DATABASE_URI, SQL_DEBUG
SQLALCHEMY_DATABASE_URI = 'sqlite:///zeitbot.db'
SQL_DEBUG = False

#import sqlalchemy
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, ForeignKey, Integer, String, Date, Float, Boolean

Base = declarative_base()
engine = create_engine(SQLALCHEMY_DATABASE_URI, echo=SQL_DEBUG)

Session = sessionmaker(bind=engine)

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
        
Base.metadata.create_all(engine)
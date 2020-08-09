import json

from sqlalchemy import Column, String, Integer, Float, Text
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import Session

db_string = 'postgres://nms_user:nms_password@localhost/rasa'
db = create_engine(db_string)
base = declarative_base()


class Events(base):
    __tablename__ = 'events'
    
    id = Column(Integer, primary_key=True)
    sender_id = Column(String)
    type_name = Column(String)
    timestamp = Column(Float)
    intent_name = Column(String)
    action_name = Column(String)
    data = Column(Text)

    def __str__(self):
        return '{}|{}|{}|{}|{}|{}|{}'.format(self.id, self.sender_id, self.type_name, self.timestamp, self.intent_name, self.action_name, self.data)

class TextUser(base):
    __tablename__ = 'TextUser'
    text_user = Column(String, primary_key=True)
    timestamp = Column(Float)
    entity = Column(String)
    intent = Column(String)
    def __init__(self,text_user, timestamp, entity, intent):
        self.text_user = text_user
        self.timestamp = timestamp
        self.entity = entity
        self.intent = intent
        

if __name__ == "__main__":
    base.metadata.create_all(db)
    
    Session = sessionmaker(db)
    session = Session()
    
    events = session.query(Events).filter(Events.type_name == 'user')
    session.commit()
    for event in events:
        data = json.loads(event.data)
        text = data['text']
        if text[0] != '/' and text[:8] != 'EXTERNAL':
            timestamp = data['timestamp']
            try:
                entity = json.dumps(data['parse_data']['entities'])
            except:
                entity = None
            try:
                intent = json.dumps(data['parse_data']['intent_ranking'])
            except:
                intent = None
            textUser = TextUser(text, timestamp, entity, intent)
            try:
                session.add(textUser)
                session.commit()
                # print('adding')
            except:
                session.rollback()
                
            
        else:
            continue
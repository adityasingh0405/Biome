import random
import pandas as pd
from faker import Faker
from sqlalchemy import create_engine

# 1. Connection string for your local PostgreSQL
# Format: postgresql://username:password@localhost:5432/database_name
DB_URI = "postgresql://postgres:Aditya%402005@localhost:5432/enterprise_rag"
engine = create_engine(DB_URI)

fake = Faker()

def generate_enterprise_data(num_rows=1000):
    print(f"Generating {num_rows} fake enterprise records...")
    data = []
    
    priorities = ['Low', 'Medium', 'High', 'Critical']
    departments = ['Logistics', 'Operations', 'HR', 'Engineering', 'Customer Support']

    for _ in range(num_rows):
        data.append({
            'ticket_id': fake.uuid4(),
            'department': random.choice(departments),
            'route_or_system': f"SYS-{random.randint(100, 999)}",
            'issue_summary': fake.sentence(nb_words=6),
            'detailed_description': fake.paragraph(nb_sentences=3),
            'created_at': fake.date_time_this_year(),
            'priority_level': random.choice(priorities),
            'resolved': random.choice([True, False])
        })
        
    return pd.DataFrame(data)

if __name__ == "__main__":
    # Generate the dataframe
    df = generate_enterprise_data(1000)
    
    # Push data straight into local PostgreSQL table named 'enterprise_tickets'
    # if_exists='replace' creates the table automatically if it doesn't exist
    df.to_sql('enterprise_tickets', engine, if_exists='replace', index=False)
    
    print("Database successfully populated with 1,000 rows!")

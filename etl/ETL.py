import requests
import psycopg2
import json
from dotenv import load_dotenv
import os
import re
from datetime import datetime

def run_etl(DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASS, MAIL) -> int:
    OPENALEX_URL = "https://api.openalex.org/works"
    PARAMS = {
    "per-page": 100,               
    "page": 1,
    "mailto": MAIL}

    # extract data from OpenAlex
    response = requests.get(OPENALEX_URL, params=PARAMS)
    data = response.json() if response.status_code == 200 else None

    if data is None:
        raise Exception(f"Error al obtener datos de OpenAlex: {response.status_code} - {response.text}")

    works = data.get("results", [])
    print(f"Total rows received: {len(works)}")  # Verificación simple

    # data processing and normalization
    rows = []
    for w in works:
            #get unique id from openAlex URI,
            rid = (w.get("id") or "").split("/")[-1]
            doi = w.get("doi")

            raw_title = w.get("title") or w.get("display_name") or ""
            # Normalize title, convert to lowercase and delete special characters if exists
            title = raw_title.lower()
            title = re.sub(r"[^a-z0-9 ]", "", title)

            publication_year = w.get("publication_year")


            # Formating date to DD-MM-YYYY

            raw_date = w.get("publication_date")
            dt = datetime.strptime(raw_date, "%Y-%m-%d")
            publication_date = dt.strftime("%d-%m-%Y")

            language = w.get("language")

            # Extract host organization name if exists
            cited_by_count = w.get("cited_by_count")
            # list of referenced works
            referenced_works = w.get("referenced_works", [])
            # add tuple to list

            rows.append([
                rid, doi, title,
                publication_year, publication_date,
                language, cited_by_count,
                json.dumps(referenced_works)
            ])

    # 3. load data to PGDB
    conn = psycopg2.connect(host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASS)
    cur = conn.cursor()

    # Create table if not exists
    create_table_query = """
    CREATE TABLE IF NOT EXISTS works (
        id TEXT,
        doi TEXT,
        title TEXT,
        publication_year INT,
        publication_date DATE,
        language TEXT,
        cited_by_count TEXT,
        referenced_works JSONB
    );
    """
    cur.execute(create_table_query)
    conn.commit()

    # Insert data in table
    insert_query = """
    INSERT INTO works (
        id, doi, title,
        publication_year, publication_date,
        language, cited_by_count, referenced_works
    ) VALUES (
        %s, %s, %s,
        %s, %s,
        %s, %s, %s
    )    ON CONFLICT (id) DO UPDATE SET
        doi = EXCLUDED.doi,
        title = EXCLUDED.title,
        publication_year = EXCLUDED.publication_year,
        publication_date = EXCLUDED.publication_date,
        language = EXCLUDED.language,
        cited_by_count = EXCLUDED.cited_by_count,
        referenced_works = EXCLUDED.referenced_works;
    """
    # execute insert
    cur.executemany(insert_query, rows)
    conn.commit()

    data = cur.rowcount
    print(f"{data} registros insertados/actualizados en la base de datos.")
    cur.close()
    conn.close()
    return data

#run directly the ETL
if __name__ == "__main__":
    load_dotenv(dotenv_path='../.env')
    DB_HOST = os.getenv("DB_HOST")
    DB_NAME = os.getenv("DB_NAME")
    DB_USER = os.getenv("DB_USER")
    DB_PASS = os.getenv("DB_PASS")
    DB_PORT = os.getenv("DB_PORT")
    MAIL = os.getenv("MAIL")
    run_etl(DB_HOST, DB_PORT, DB_NAME,DB_USER, DB_PASS, MAIL)
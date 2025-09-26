from fastapi import FastAPI, HTTPException, Depends
from dotenv import load_dotenv
import os
import psycopg2
import os, sys, subprocess, psycopg2
from fastapi.security.api_key import APIKeyHeader

load_dotenv(dotenv_path='../.env')

# Database variables configuration
DB_HOST = os.getenv("DB_HOST")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_PORT = os.getenv("DB_PORT")
MAIL = os.getenv("MAIL")
API_TOKEN = os.getenv("API_TOKEN")


app = FastAPI(title="OpenAlex Works API")


api_key_header = APIKeyHeader(name="X-API-Key", auto_error=True)

def verify_token(api_key: str = Depends(api_key_header)):
    if api_key != API_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")
# Helper: convert row to dict
def row_to_dict(cur, row):
    col_names = [desc[0] for desc in cur.description]
    record = {}
    for col, val in zip(col_names, row):
        if isinstance(val, (bytes, bytearray)):
            # Convertir campos binarios (si los hubiera) a string
            record[col] = val.decode() if isinstance(val, bytes) else str(val)
        else:
            record[col] = val
    return record


# try to import etl as a module
RUNS_AS_MODULE = False
try:
    # add /etl to path
    ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    ELT_DIR = os.path.join(ROOT_DIR, "etl")
    if ELT_DIR not in sys.path:
        sys.path.insert(0, ELT_DIR)
    import etl  # epose run_etl() function
    RUNS_AS_MODULE = hasattr(etl, "run_etl")
except Exception:
    RUNS_AS_MODULE = False




@app.get("/records", summary="get all registers")
def list_records():
    """list all rows in BD"""
    with psycopg2.connect(host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASS) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM works;")
            rows = cur.fetchall()
            results = [row_to_dict(cur, row) for row in rows]
    return {"results": results, "total": len(results)}


@app.get("/records/{record_id:path}", summary="obtain a register by ID")
def get_record_by_id(record_id: str):
    """
    the ID can be the opwn ALEX id (e.g 'W2768643452').
    also accepts, e.g. 'https://openalex.org/W2768643452'.
    """
    # if id contains http, obtain the last parameter
    if record_id.startswith("http"):
        record_id = record_id.split("/")[-1]
    with psycopg2.connect(host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASS) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM works WHERE id = %s;", (record_id,))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Registro no encontrado")
            record = row_to_dict(cur, row)
    return record



@app.get("/filter", summary="search registers by keyword, year or language")
def search_records(keyword: str = None, year: int = None, language: str = None):
    """
    Search registers filtering by keyword on DOI, year or language
    - keyword: string to search in DOI
    - year: filters by publish year
    - language: filters by language code e.g es, en
    """
    # build dinamycally the query
    base_query = "SELECT * FROM works"
    conditions = []
    params = []
    if keyword:
        conditions.append("(title ILIKE %s)")
        kw_param = f"%{keyword}%"
        params.extend([kw_param])
    if year:
        conditions.append("publication_year = %s")
        params.append(year)
    if language:
        conditions.append("language = %s")
        params.append(language)
    if conditions:
        query = f"{base_query} WHERE " + " AND ".join(conditions) + ";"
    else:
        query = base_query + ";"  # if not filters applied, return everything
    # Ejecutar la consulta
    with psycopg2.connect(host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASS) as conn:
        with conn.cursor() as cur:
            cur.execute(query, tuple(params))
            rows = cur.fetchall()
            results = [row_to_dict(cur, row) for row in rows]
    return {"results": results, "total": len(results)}



@app.post("/update", summary="update data from etl", dependencies=[Depends(verify_token)])
def update_data():
    # Truncate data before loading
    try:
        with psycopg2.connect(host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASS) as conn:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE TABLE works;")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al truncar tabla: {e}")
    
    # Execute the ETL
    try:
        if RUNS_AS_MODULE:
            # calls etl.py function
            inserted = etl.run_etl(
                db_host=DB_HOST, db_port=DB_PORT,
                db_name=DB_NAME, db_user=DB_USER, db_pass=DB_PASS
            )
        else:
            # Ejecutar como script: python /project/elt/etl.py
            ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            etl_script = os.path.join(ROOT_DIR, "etl", "ETL.py")
            proc = subprocess.run(
                [sys.executable, etl_script],
                capture_output=True, text=True, check=True
            )
            inserted = None
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"ETL (script) falló: {e.stderr.strip()}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ETL (módulo) falló: {e}")
    return {"status": "success", "message": "Tabla vaciada y ETL ejecutada."}

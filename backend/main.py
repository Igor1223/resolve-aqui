import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from jose import jwt, JWTError
from pwdlib import PasswordHash
from pydantic import BaseModel, EmailStr, Field

ROOT = Path(__file__).resolve().parent.parent
DB_URL = os.getenv("DATABASE_URL", "sqlite:///./resolve_aqui.db")
DB_PATH = DB_URL.replace("sqlite:///", "") if DB_URL.startswith("sqlite:///") else str(ROOT / "resolve_aqui.db")
if not DB_PATH.startswith("/"):
    DB_PATH = str(ROOT / DB_PATH)
SECRET = os.getenv("SECRET_KEY", "dev-only-change-this-secret-before-deploying")
ALGORITHM = "HS256"
password_hash = PasswordHash.recommended()

GUIDES = [
 {"title":"Emitir ou consultar o CPF","category":"Documentos","summary":"Consulte os canais oficiais para verificar sua situação cadastral ou acessar serviços relacionados ao CPF.","steps":["Acesse a página oficial da Receita Federal.","Escolha o serviço adequado: consulta, atualização ou comprovante.","Siga as instruções do portal oficial."],"documents":["Número do CPF","Documento de identificação, quando solicitado"],"url":"https://www.gov.br/receitafederal/pt-br/assuntos/meu-cpf","warning":"As exigências variam conforme o serviço. Confira as instruções oficiais."},
 {"title":"Consultar benefício do INSS","category":"Benefícios","summary":"Acesse o canal oficial para acompanhar benefícios e pedidos previdenciários.","steps":["Entre no Meu INSS pelo site ou aplicativo oficial.","Acesse com sua conta gov.br.","Localize o benefício ou requerimento desejado.","Confira eventuais exigências e mensagens."],"documents":["CPF","Conta gov.br","Número do benefício ou protocolo, se houver"],"url":"https://meu.inss.gov.br/","warning":"O Resolve Aqui não concede nem altera benefícios. A análise é feita pelo INSS."},
 {"title":"Encontrar uma Unidade Básica de Saúde","category":"Saúde","summary":"Veja como localizar a unidade de saúde responsável pelo seu endereço.","steps":["Consulte a Secretaria de Saúde ou a prefeitura do município.","Confirme qual UBS atende seu endereço.","Verifique horário, agendamento e documentos antes de sair."],"documents":["Documento de identificação","Cartão SUS, se tiver","Comprovante de residência, se solicitado"],"url":"https://www.gov.br/saude/pt-br","warning":"Em emergência, procure atendimento de urgência ou ligue 192 (SAMU)."},
 {"title":"Descartar medicamentos vencidos","category":"Meio ambiente","summary":"Saiba como encaminhar medicamentos vencidos ou sem uso para um ponto de coleta.","steps":["Mantenha o medicamento na embalagem original, se possível.","Procure farmácia ou ponto de coleta que receba medicamentos domiciliares.","Confirme previamente o que o local aceita.","Entregue diretamente no ponto de coleta."],"documents":["Normalmente não é necessário apresentar documentos"],"url":"https://www.gov.br/anvisa/pt-br","warning":"A disponibilidade varia por município. Confirme com a farmácia ou prefeitura."},
 {"title":"Acessar serviços pelo gov.br","category":"Serviços digitais","summary":"Entenda como entrar na conta gov.br e localizar serviços públicos digitais.","steps":["Acesse o portal gov.br.","Entre com CPF e senha da sua conta.","Pesquise o serviço desejado.","Confira se o endereço é realmente gov.br antes de informar dados."],"documents":["CPF","Acesso ao e-mail ou telefone cadastrado, se for necessária validação"],"url":"https://www.gov.br/","warning":"Nunca compartilhe senha ou códigos de autenticação. O Resolve Aqui não solicita esses dados."}
]

@contextmanager
def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    try:
        yield con
        con.commit()
    finally:
        con.close()

def init_db():
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    with db() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS guides(id INTEGER PRIMARY KEY, title TEXT NOT NULL, category TEXT NOT NULL, summary TEXT NOT NULL, steps TEXT NOT NULL, documents TEXT NOT NULL, url TEXT NOT NULL, warning TEXT NOT NULL, verified_at TEXT);
        CREATE TABLE IF NOT EXISTS favorites(user_id INTEGER NOT NULL, guide_id INTEGER NOT NULL, PRIMARY KEY(user_id,guide_id), FOREIGN KEY(user_id) REFERENCES users(id), FOREIGN KEY(guide_id) REFERENCES guides(id));
        CREATE TABLE IF NOT EXISTS consultations(id INTEGER PRIMARY KEY, user_id INTEGER NOT NULL, question TEXT NOT NULL, answer TEXT NOT NULL, created_at TEXT NOT NULL, FOREIGN KEY(user_id) REFERENCES users(id));
        """)
        if con.execute("SELECT COUNT(*) FROM guides").fetchone()[0] == 0:
            for g in GUIDES:
                con.execute("INSERT INTO guides(title,category,summary,steps,documents,url,warning,verified_at) VALUES(?,?,?,?,?,?,?,?)",
                    (g["title"],g["category"],g["summary"],json.dumps(g["steps"],ensure_ascii=False),json.dumps(g["documents"],ensure_ascii=False),g["url"],g["warning"],None))

@contextmanager
def startup():
    init_db()
    yield

app = FastAPI(title="Resolve Aqui API", version="1.0.0", lifespan=startup)
origins = [x.strip() for x in os.getenv("CORS_ORIGINS","*").split(",")]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=origins != ["*"], allow_methods=["*"], allow_headers=["*"])
WEB = ROOT / "web"
if WEB.exists():
    app.mount("/static", StaticFiles(directory=WEB), name="static")

class Register(BaseModel):
    name: str = Field(min_length=2,max_length=80)
    email: EmailStr
    password: str = Field(min_length=8,max_length=128)
class Login(BaseModel):
    email: EmailStr
    password: str
class GuideIn(BaseModel):
    title: str
    category: str
    summary: str
    steps: list[str]
    documents: list[str]
    url: str
    warning: str
class Ask(BaseModel):
    question: str = Field(min_length=4,max_length=2000)

def token_for(user):
    return jwt.encode({"sub":str(user["id"]),"exp":datetime.now(timezone.utc)+timedelta(days=7)},SECRET,algorithm=ALGORITHM)

def current_user(authorization: Optional[str] = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401,"Faça login para continuar.")
    try:
        payload=jwt.decode(authorization[7:],SECRET,algorithms=[ALGORITHM])
        uid=int(payload["sub"])
    except (JWTError,ValueError,KeyError):
        raise HTTPException(401,"Sessão inválida ou expirada.")
    with db() as con:
        user=con.execute("SELECT id,name,email FROM users WHERE id=?",(uid,)).fetchone()
    if not user: raise HTTPException(401,"Usuário não encontrado.")
    return dict(user)

def guide_dict(r):
    return {"id":r["id"],"title":r["title"],"category":r["category"],"summary":r["summary"],"steps":json.loads(r["steps"]),"documents":json.loads(r["documents"]),"url":r["url"],"warning":r["warning"],"verified_at":r["verified_at"]}

@app.get("/api/health")
def health(): return {"status":"ok","app":"Resolve Aqui API","version":"1.0.0"}

@app.get("/")
def home():
    index=WEB/"index.html"
    if index.exists(): return FileResponse(index)
    return {"message":"Resolve Aqui API online","docs":"/docs"}

@app.post("/api/auth/register",status_code=201)
def register(data:Register):
    with db() as con:
        if con.execute("SELECT 1 FROM users WHERE email=?",(data.email.lower(),)).fetchone():
            raise HTTPException(409,"Este e-mail já está cadastrado.")
        cur=con.execute("INSERT INTO users(name,email,password_hash,created_at) VALUES(?,?,?,?)",
            (data.name.strip(),data.email.lower(),password_hash.hash(data.password),datetime.now(timezone.utc).isoformat()))
        user={"id":cur.lastrowid,"name":data.name.strip(),"email":data.email.lower()}
    return {"access_token":token_for(user),"token_type":"bearer","user":user}

@app.post("/api/auth/login")
def login(data:Login):
    with db() as con: user=con.execute("SELECT * FROM users WHERE email=?",(data.email.lower(),)).fetchone()
    if not user or not password_hash.verify(data.password,user["password_hash"]):
        raise HTTPException(401,"E-mail ou senha incorretos.")
    public={"id":user["id"],"name":user["name"],"email":user["email"]}
    return {"access_token":token_for(public),"token_type":"bearer","user":public}

@app.get("/api/me")
def me(user=Depends(current_user)): return user

@app.get("/api/categories")
def categories():
    with db() as con: rows=con.execute("SELECT DISTINCT category FROM guides ORDER BY category").fetchall()
    return ["Todas"]+[r[0] for r in rows]

@app.get("/api/guides")
def list_guides(q:str=Query(default="",max_length=120),category:str="Todas"):
    sql="SELECT * FROM guides WHERE 1=1"; args=[]
    if q.strip():
        term=f"%{q.strip()}%"; sql+=" AND (title LIKE ? OR summary LIKE ? OR category LIKE ?)"; args += [term,term,term]
    if category!="Todas": sql+=" AND category=?"; args.append(category)
    sql+=" ORDER BY category,title"
    with db() as con: rows=con.execute(sql,args).fetchall()
    return [guide_dict(r) for r in rows]

@app.get("/api/guides/{guide_id}")
def get_guide(guide_id:int):
    with db() as con: r=con.execute("SELECT * FROM guides WHERE id=?",(guide_id,)).fetchone()
    if not r: raise HTTPException(404,"Guia não encontrado.")
    return guide_dict(r)

@app.get("/api/favorites")
def favorites(user=Depends(current_user)):
    with db() as con: rows=con.execute("SELECT g.* FROM guides g JOIN favorites f ON f.guide_id=g.id WHERE f.user_id=? ORDER BY g.title",(user["id"],)).fetchall()
    return [guide_dict(r) for r in rows]

@app.post("/api/favorites/{guide_id}",status_code=204)
def add_favorite(guide_id:int,user=Depends(current_user)):
    with db() as con:
        if not con.execute("SELECT 1 FROM guides WHERE id=?",(guide_id,)).fetchone(): raise HTTPException(404,"Guia não encontrado.")
        con.execute("INSERT OR IGNORE INTO favorites(user_id,guide_id) VALUES(?,?)",(user["id"],guide_id))
    return None

@app.delete("/api/favorites/{guide_id}",status_code=204)
def remove_favorite(guide_id:int,user=Depends(current_user)):
    with db() as con: con.execute("DELETE FROM favorites WHERE user_id=? AND guide_id=?",(user["id"],guide_id))
    return None

@app.get("/api/history")
def history(user=Depends(current_user)):
    with db() as con: rows=con.execute("SELECT id,question,answer,created_at FROM consultations WHERE user_id=? ORDER BY id DESC LIMIT 30",(user["id"],)).fetchall()
    return [dict(r) for r in rows]

@app.post("/api/assistant")
def assistant(data:Ask,user=Depends(current_user)):
    api_key=os.getenv("OPENAI_API_KEY")
    if not api_key: raise HTTPException(503,"Assistente de IA ainda não configurado. Adicione OPENAI_API_KEY no ambiente do servidor.")
    try:
        from openai import OpenAI
        client=OpenAI(api_key=api_key)
        with db() as con: guides=con.execute("SELECT title,summary,steps,url,warning FROM guides").fetchall()
        context=json.dumps([dict(g) for g in guides],ensure_ascii=False)
        response=client.chat.completions.create(model=os.getenv("OPENAI_MODEL","gpt-4.1-mini"),messages=[
          {"role":"system","content":"Você é o assistente do Resolve Aqui. Responda em português simples, com empatia e passos práticos. Use o contexto fornecido como base. Não invente endereço, horário, requisito ou regra. Se não houver informação suficiente, diga isso e indique o canal oficial. Nunca peça senhas, códigos de autenticação ou dados bancários. Não substitua profissionais de saúde ou advogados. Diferencie claramente orientação geral de informação confirmada. Contexto de guias cadastrados: "+context},
          {"role":"user","content":data.question}
        ],temperature=0.2)
        answer=response.choices[0].message.content or "Não consegui formular uma orientação agora."
    except Exception:
        raise HTTPException(502,"Não foi possível consultar a IA neste momento.")
    with db() as con:
        con.execute("INSERT INTO consultations(user_id,question,answer,created_at) VALUES(?,?,?,?)",(user["id"],data.question,answer,datetime.now(timezone.utc).isoformat()))
    return {"answer":answer,"disclaimer":"Confira informações importantes nos canais oficiais."}

def admin_guard(x_admin_key:Optional[str]=Header(default=None)):
    expected=os.getenv("ADMIN_API_KEY")
    if not expected or x_admin_key != expected: raise HTTPException(403,"Acesso administrativo não autorizado.")

@app.post("/api/admin/guides",status_code=201)
def create_guide(data:GuideIn,_=Depends(admin_guard)):
    with db() as con:
        cur=con.execute("INSERT INTO guides(title,category,summary,steps,documents,url,warning) VALUES(?,?,?,?,?,?,?)",
          (data.title,data.category,data.summary,json.dumps(data.steps,ensure_ascii=False),json.dumps(data.documents,ensure_ascii=False),data.url,data.warning))
    return {"id":cur.lastrowid,"message":"Guia cadastrado. Revise a fonte oficial antes de publicar."}

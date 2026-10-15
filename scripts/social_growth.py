import os,json,re,html,base64,hashlib
from datetime import datetime,timedelta,timezone
from urllib.parse import urlsplit,urlunsplit,parse_qsl,urlencode
from pathlib import Path
import requests

BASE=os.environ.get("WP_BASE_URL","").rstrip("/")
MODE=os.environ.get("SOCIAL_PUBLISH_MODE","dry-run")
REPORT=Path("social_growth_report.json")
GH="https://api.github.com/repos/"+os.environ.get("GITHUB_REPOSITORY","")
HEAD={"Authorization":"Bearer "+os.environ.get("GITHUB_TOKEN",""),"Accept":"application/vnd.github+json","X-GitHub-Api-Version":"2022-11-28"}
STATE="data/facebook_growth.json"
BRANCH="social-state"

def get_json(url,headers=None,params=None):
    r=requests.get(url,headers=headers,params=params,timeout=25)
    r.raise_for_status()
    return r.json()

def clean(s):
    return re.sub(r"\s+"," ",html.unescape(re.sub(r"<[^>]+>"," ",str(s)))).strip()

def tracked(post):
    url=urlsplit(post["link"])
    host=urlsplit(BASE)
    if url.scheme!="https" or url.netloc!=host.netloc or url.username or url.password:
        raise ValueError("URL esterno o non sicuro")
    query=[(k,v) for k,v in parse_qsl(url.query) if not k.startswith("utm_")]
    query += [("utm_source","facebook"),("utm_medium","organic_social"),("utm_campaign","aivision_traffic"),("utm_content","wp_"+str(post["id"]))]
    return urlunsplit((url.scheme,url.netloc,url.path,urlencode(query),""))

def caption(post):
    title=clean(post["title"]["rendered"])[:180]
    summary=clean(post.get("excerpt",{}).get("rendered",""))[:230]
    questions=["Cosa ne pensi?","Quali conseguenze potrebbe avere?","Quale aspetto approfondiresti?"]
    q=questions[int(hashlib.sha256(str(post["id"]).encode()).hexdigest(),16)%len(questions)]
    return "\n\n".join([title]+([summary] if summary else [])+[q,"Approfondisci su AIVision. #AIVision"])

def github(method,path,payload=None):
    r=requests.request(method,GH+path,headers=HEAD,json=payload,timeout=25)
    if r.status_code==404 and method=="GET": return None
    r.raise_for_status()
    return r.json()

def load_state():
    ref=github("GET","/git/ref/heads/"+BRANCH)
    if ref is None:
        default=github("GET","")["default_branch"]
        base=github("GET","/git/ref/heads/"+default)["object"]["sha"]
        github("POST","/git/refs",{"ref":"refs/heads/"+BRANCH,"sha":base})
    file=github("GET","/contents/"+STATE+"?ref="+BRANCH)
    if file is None: return None,None
    return json.loads(base64.b64decode(file["content"])),file["sha"]

def save_state(state,sha):
    body={"branch":BRANCH,"message":"Update Facebook delivery state [skip ci]","content":base64.b64encode(json.dumps(state).encode()).decode()}
    if sha: body["sha"]=sha
    return github("PUT","/contents/"+STATE,body)["content"]["sha"]

def main():
    report={"mode":MODE,"status":"off","published":[],"warnings":[]}
    try:
        if MODE not in ("off","dry-run","live"): raise ValueError("Modalita social non valida")
        if MODE=="off": return report
        if urlsplit(BASE).scheme!="https": raise ValueError("WP_BASE_URL HTTPS mancante")
        posts=get_json(BASE+"/wp-json/wp/v2/posts",params={"status":"publish","per_page":100,"orderby":"date","order":"desc"})
        now=datetime.now(timezone.utc)
        eligible=[]
        for p in posts:
            if p.get("status")!="publish":continue
            try:
                date=datetime.fromisoformat(p["date_gmt"].replace("Z","+00:00")).replace(tzinfo=timezone.utc)
                if now-timedelta(hours=96)<=date<=now:
                    tracked(p)
                    eligible.append(p)
            except (ValueError,KeyError,TypeError):continue
        eligible.reverse()
        report["eligible"]=len(eligible)
        if MODE=="dry-run":
            report["status"]="preview"
            report["preview"]=[{"id":p["id"],"caption":caption(p),"link":tracked(p)} for p in eligible[-2:]]
            return report
        token=os.getenv("SOCIAL_FB_PAGE_TOKEN","")
        page=os.getenv("SOCIAL_FB_PAGE_ID","")
        if not token or not page:
            report["status"]="not_configured"
            report["warnings"].append("Servono ID e token della Pagina Meta")
            return report
        version=os.getenv("SOCIAL_GRAPH_VERSION","v25.0")
        if not re.fullmatch(r"v\d+\.\d+",version) or not page.isdigit():raise ValueError("Configurazione Meta non valida")
        root="https://graph.facebook.com/"+version
        me=get_json(root+"/me",headers={"Authorization":"Bearer "+token},params={"fields":"id,name"})
        if str(me.get("id"))!=page:raise ValueError("Token non appartenente alla Pagina")
        state,sha=load_state()
        if state is None:
            state={"site":BASE,"page":page,"posts":{str(p["id"]):{"status":"baseline"} for p in eligible}}
            save_state(state,sha)
            report["status"]="baseline"
            return report
        if state["site"]!=BASE or state["page"]!=page:raise ValueError("Registro collegato ad altra Pagina")
        sent=[datetime.fromisoformat(v["at"]) for v in state["posts"].values() if v.get("status")=="sent"]
        today=now.date()
        if sum(x.date()==today for x in sent)>=5 or any(x>now-timedelta(minutes=45) for x in sent):
            report["status"]="rate_limited"
            return report
        for p in eligible:
            key=str(p["id"])
            if key in state["posts"]:continue
            url=tracked(p)
            check=requests.get(p["link"],timeout=25,allow_redirects=False)
            if check.status_code!=200:continue
            state["posts"][key]={"status":"pending","at":now.isoformat()}
            sha=save_state(state,sha)
            response=requests.post(root+"/"+page+"/feed",headers={"Authorization":"Bearer "+token},data={"message":caption(p),"link":url},timeout=25)
            response.raise_for_status()
            result=response.json()
            if "id" not in result:raise ValueError("Meta non ha restituito ID; invio pending")
            state["posts"][key]={"status":"sent","at":now.isoformat(),"fb_id":result["id"]}
            sha=save_state(state,sha)
            report["published"].append({"wp_id":p["id"],"facebook_id":result["id"]})
            break
        report["status"]="ok"
    except Exception as e:
        report["status"]="error"
        report["warnings"].append(type(e).__name__+": "+str(e).split("https://")[0][:150])
    return report

if __name__=="__main__":
    result=main()
    REPORT.write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result,indent=2))
    if result["status"]=="error":raise SystemExit(1)

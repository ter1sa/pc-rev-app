from fastapi import FastAPI
from DBLP import connectToDBLPPage, xmlifyAdd, readAuthorDBLP

app = FastAPI()

@app.get("/dblp/{dblp_url:path}")
async def get_dblp_data(dblp_url: str):
    print(f"Received DBLP URL: {dblp_url}")
    xml_url = xmlifyAdd(dblp_url)
    xml_data = connectToDBLPPage(xml_url)
    if not xml_data:
        return {"error": "Could not retrieve DBLP data"}
    
    person, _, coauthor_hist, _, years_of_pub, coauthor_set, _ = readAuthorDBLP(xml_data, {}, {}, {}, dblp_url)
    return {
        "person_name": person,
        "coauthor_hist": coauthor_hist,
        "years_of_publication": list(years_of_pub),
        "coauthors": list(coauthor_set)
    }

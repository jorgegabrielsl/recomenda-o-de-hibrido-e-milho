import requests


def testar_api():
    url =(
        "https://servicodados.ibge.gov.br/api/v3/"
        "agregados/1612/periodos/2024/variaveis/214"
    )

    params = {
        "localidades":"N6[4200051]",
        "classificacao":"81[2711]"
    }


    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/152.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json,text/plain,*/*",
        "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
        "Referer": "https://servicodados.ibge.gov.br/"
    }

    with requests.Session() as session:
        response = session.get(
            url,
            params = params, 
            headers = headers,
            timeout=60,
        )


        print("STATUS:",response.status_code)
        print("URL:",response.url)

if __name__ == "__main__":
    testar_api()

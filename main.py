import streamlit as st
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# ---------------------------------------------------------
# 1. 기본 페이지 설정
# ---------------------------------------------------------

st.set_page_config(
    page_title="어제의 박스오피스",
    page_icon="🎬",
    layout="wide"
)


# ---------------------------------------------------------
# 2. 제목
# ---------------------------------------------------------

st.title("🎬 어제의 박스오피스")
st.caption("한국시간 기준으로 어제 하루 동안의 영화 박스오피스입니다.")


# ---------------------------------------------------------
# 3. 한국 시간 기준으로 '어제' 날짜 계산
# ---------------------------------------------------------
# 배포 서버의 시간이 한국 시간이 아닐 수 있기 때문에
# 반드시 한국 시간(Asia/Seoul)을 기준으로 날짜를 계산합니다.

KST = ZoneInfo("Asia/Seoul")

today_kst = datetime.now(KST).date()
yesterday_kst = today_kst - timedelta(days=1)

# KOBIS API가 요구하는 날짜 형식: YYYYMMDD
target_date = yesterday_kst.strftime("%Y%m%d")

# 화면에 보여줄 날짜 형식
display_date = yesterday_kst.strftime("%Y년 %m월 %d일")


# ---------------------------------------------------------
# 4. KOBIS API 주소
# ---------------------------------------------------------

API_URL = (
    "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
    "boxoffice/searchDailyBoxOfficeList.json"
)


# ---------------------------------------------------------
# 5. KOBIS API에서 데이터 가져오기
# ---------------------------------------------------------
# @st.cache_data를 사용하면 같은 날짜의 데이터를
# 일정 시간 동안 다시 API에 요청하지 않습니다.
#
# ttl=3600 → 3600초 = 약 1시간 동안 캐시

@st.cache_data(ttl=3600)
def get_boxoffice_data(target_dt):
    """
    KOBIS에서 특정 날짜의 일일 박스오피스 데이터를 가져옵니다.

    target_dt:
        조회할 날짜. YYYYMMDD 형식의 문자열
    """

    # -----------------------------------------------------
    # secrets에서 KOBIS 인증키 가져오기
    # -----------------------------------------------------
    # 인증키를 코드에 직접 적지 않습니다.
    # Streamlit Cloud의 Secrets에 KOBIS_KEY를 저장해 둡니다.

    try:
        kobis_key = st.secrets["KOBIS_KEY"]
    except Exception:
        return {
            "success": False,
            "message": (
                "KOBIS 인증키를 찾을 수 없습니다.\n\n"
                "Streamlit Cloud의 앱 설정에서 Secrets를 열고 "
                "`KOBIS_KEY`가 등록되어 있는지 확인하세요."
            ),
            "data": []
        }

    # -----------------------------------------------------
    # API 요청에 사용할 변수
    # -----------------------------------------------------

    params = {
        "key": kobis_key,
        "targetDt": target_dt
    }

    # -----------------------------------------------------
    # API 요청
    # -----------------------------------------------------

    try:
        response = requests.get(
            API_URL,
            params=params,
            timeout=10
        )

        # HTTP 상태 코드가 200이 아닌 경우
        response.raise_for_status()

    except requests.exceptions.Timeout:
        return {
            "success": False,
            "message": (
                "KOBIS API 요청 시간이 초과되었습니다.\n\n"
                "잠시 후 다시 실행해 보세요. "
                "인터넷 연결이나 KOBIS 서버 상태도 확인해 주세요."
            ),
            "data": []
        }

    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "message": (
                "KOBIS API에 연결하지 못했습니다.\n\n"
                "인터넷 연결과 KOBIS API 서버 상태를 확인해 주세요.\n\n"
                f"오류 내용: {e}"
            ),
            "data": []
        }

    # -----------------------------------------------------
    # JSON 응답으로 변환
    # -----------------------------------------------------

    try:
        result = response.json()
    except ValueError:
        return {
            "success": False,
            "message": (
                "KOBIS API에서 정상적인 JSON 데이터를 받지 못했습니다.\n\n"
                "API 서버 상태를 확인해 주세요."
            ),
            "data": []
        }

    # -----------------------------------------------------
    # 중요!
    # 인증키가 틀려도 HTTP 상태코드는 200일 수 있습니다.
    #
    # 따라서 faultInfo가 있는지 반드시 확인합니다.
    # -----------------------------------------------------

    if "faultInfo" in result:
        fault = result["faultInfo"]

        fault_code = fault.get("errorCode", "알 수 없음")
        fault_message = fault.get(
            "message",
            "KOBIS API에서 오류가 발생했습니다."
        )

        return {
            "success": False,
            "message": (
                "KOBIS API에서 오류가 발생했습니다.\n\n"
                f"오류 코드: {fault_code}\n"
                f"오류 내용: {fault_message}\n\n"
                "가장 먼저 Streamlit Secrets의 "
                "`KOBIS_KEY` 인증키가 정확한지 확인해 주세요."
            ),
            "data": []
        }

    # -----------------------------------------------------
    # boxOfficeResult 확인
    # -----------------------------------------------------

    boxoffice_result = result.get("boxOfficeResult")

    if not boxoffice_result:
        return {
            "success": False,
            "message": (
                "박스오피스 결과(boxOfficeResult)를 찾을 수 없습니다.\n\n"
                "KOBIS API 응답 형식이나 서버 상태를 확인해 주세요."
            ),
            "data": []
        }

    # -----------------------------------------------------
    # 영화 목록 가져오기
    # -----------------------------------------------------

    movie_list = boxoffice_result.get("dailyBoxOfficeList", [])

    # 영화 목록이 비어 있는 경우
    if not movie_list:
        return {
            "success": False,
            "message": (
                f"{target_dt} 날짜의 영화 목록이 비어 있습니다.\n\n"
                "KOBIS에서 해당 날짜의 일일 박스오피스가 "
                "아직 집계되지 않았거나 데이터가 제공되지 않는 "
                "날짜인지 확인해 주세요."
            ),
            "data": []
        }

    return {
        "success": True,
        "message": "",
        "data": movie_list
    }


# ---------------------------------------------------------
# 6. 데이터 가져오기
# ---------------------------------------------------------

result = get_boxoffice_data(target_date)


# ---------------------------------------------------------
# 7. API 오류 처리
# ---------------------------------------------------------

if not result["success"]:

    st.error("데이터를 불러오지 못했습니다.")

    st.warning(result["message"])

    st.info(
        "확인할 사항\n\n"
        "1. Streamlit Secrets에 `KOBIS_KEY`가 등록되어 있는지 확인\n"
        "2. 인증키가 정확한지 확인\n"
        "3. KOBIS API 서버가 정상적으로 작동하는지 확인\n"
        "4. 해당 날짜의 박스오피스 데이터가 제공되는 날짜인지 확인"
    )

    st.stop()


# ---------------------------------------------------------
# 8. 영화 데이터 가져오기
# ---------------------------------------------------------

movies = result["data"]


# ---------------------------------------------------------
# 9. 문자열로 들어오는 숫자를 숫자형으로 변환
# ---------------------------------------------------------
# KOBIS API에서는 rank, audiCnt, audiAcc, scrnCnt 등이
# 문자열로 들어오기 때문에 정렬과 그래프를 위해 숫자로 변환합니다.

for movie in movies:

    movie["rank"] = int(movie.get("rank", 0) or 0)

    movie["audiCnt"] = int(movie.get("audiCnt", 0) or 0)

    movie["audiAcc"] = int(movie.get("audiAcc", 0) or 0)

    movie["scrnCnt"] = int(movie.get("scrnCnt", 0) or 0)

    movie["showCnt"] = int(movie.get("showCnt", 0) or 0)

    movie["rankInten"] = int(movie.get("rankInten", 0) or 0)


# ---------------------------------------------------------
# 10. 순위 기준으로 정렬
# ---------------------------------------------------------

movies.sort(key=lambda x: x["rank"])


# ---------------------------------------------------------
# 11. 조회 날짜 표시
# ---------------------------------------------------------

st.subheader(f"📅 {display_date} 박스오피스")

st.caption(
    f"KOBIS 조회 날짜: {target_date} · "
    f"한국시간 기준 어제 데이터"
)


# ---------------------------------------------------------
# 12. 1위 영화 찾기
# ---------------------------------------------------------

first_movie = movies[0]

first_movie_name = first_movie.get("movieNm", "영화명 없음")
first_audi_cnt = first_movie["audiCnt"]
first_audi_acc = first_movie["audiAcc"]
first_scrn_cnt = first_movie["scrnCnt"]


# ---------------------------------------------------------
# 13. 1위 영화 크게 보여주기
# ---------------------------------------------------------

st.markdown(f"## 🥇 1위: {first_movie_name}")


# 지표 카드 3개를 만듭니다.
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        label="🎟️ 어제 관객수",
        value=f"{first_audi_cnt:,}명"
    )

with col2:
    st.metric(
        label="👥 누적 관객수",
        value=f"{first_audi_acc:,}명"
    )

with col3:
    st.metric(
        label="🖥️ 스크린수",
        value=f"{first_scrn_cnt:,}개"
    )


st.divider()


# ---------------------------------------------------------
# 14. 관객수 상위 5편 막대그래프
# ---------------------------------------------------------

st.subheader("📊 관객수 상위 5편")


# 관객수가 많은 순서대로 정렬
top5 = sorted(
    movies,
    key=lambda x: x["audiCnt"],
    reverse=True
)[:5]


# Streamlit의 bar_chart에서 사용할 데이터를 만듭니다.
# 영화명을 index로 사용하고 관객수를 열로 사용합니다.

import pandas as pd

chart_data = pd.DataFrame({
    "영화명": [movie["movieNm"] for movie in top5],
    "관객수": [movie["audiCnt"] for movie in top5]
})

chart_data = chart_data.set_index("영화명")


st.bar_chart(
    chart_data,
    y="관객수"
)


st.caption("※ 막대가 길수록 해당 날짜의 관객수가 많습니다.")


st.divider()


# ---------------------------------------------------------
# 15. 전체 영화 표 만들기
# ---------------------------------------------------------

st.subheader("🎬 전체 박스오피스")


# 화면에 보여줄 데이터만 별도로 만듭니다.

table_data = []

for movie in movies:

    table_data.append({
        "순위": movie["rank"],
        "영화명": movie.get("movieNm", ""),
        "개봉일": movie.get("openDt", ""),
        "관객수": movie["audiCnt"],
        "누적관객": movie["audiAcc"],
        "스크린수": movie["scrnCnt"]
    })


df = pd.DataFrame(table_data)


# ---------------------------------------------------------
# 16. 숫자에 천 단위 쉼표를 표시
# ---------------------------------------------------------
# 데이터 자체는 숫자형으로 유지하면서 화면에서는
# 읽기 편하게 천 단위 쉼표를 표시합니다.

st.dataframe(
    df.style.format({
        "관객수": "{:,}",
        "누적관객": "{:,}",
        "스크린수": "{:,}"
    }),
    use_container_width=True,
    hide_index=True
)


# ---------------------------------------------------------
# 17. 하단 안내
# ---------------------------------------------------------

st.divider()

st.caption(
    "데이터 출처: 영화진흥위원회(KOBIS) 일일 박스오피스 API"
)

st.caption(
    "※ API 데이터가 아직 집계되지 않았거나 KOBIS 서버에 문제가 "
    "있는 경우 결과가 표시되지 않을 수 있습니다."
)

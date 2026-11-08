import re
import logging
import time
from pathlib import Path
from shapely.geometry import mapping
from urllib.parse import quote_plus

import folium
import geopandas as gpd
import pandas as pd
import plotly.express as px
import streamlit as st
from branca.colormap import LinearColormap
from streamlit_folium import st_folium

from src.data_loader import CRITERIA, load_real_scores
from src.scoring import calculate_index

st.set_page_config(
    page_title="Mesto",
    page_icon="🏙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&family=Manrope:wght@400;500;600;700;800&display=swap');
:root{--ink:#17231f;--muted:#75817b;--green:#245c49;--green2:#367a60;--lime:#d7f36b;--paper:#f5f7f3;--line:#e3e9e2;--card:#fff}
html,body,[class*="css"]{font-family:'DM Sans',sans-serif;color:var(--ink)}
.stApp{background:var(--paper)}#MainMenu,footer{visibility:hidden}[data-testid="stSidebar"]{display:none}
header[data-testid="stHeader"]{background:rgba(245,247,243,.9)!important;backdrop-filter:blur(14px);height:3rem}
.block-container{max-width:1680px;padding:1.2rem 2.4rem 3rem}
h1,h2,h3{font-family:'Manrope',sans-serif;color:var(--ink);letter-spacing:-.055em;font-weight:800}
h1{font-size:clamp(2rem,4vw,3.5rem)}h2{font-size:2rem}h3{font-size:1.35rem}
.top-brand{font-family:'Manrope',sans-serif;font-size:1.85rem;font-weight:800;letter-spacing:-.075em;color:var(--ink);line-height:1}
.top-brand:before{content:"";display:inline-block;width:11px;height:11px;background:var(--lime);border:2px solid var(--green);border-radius:4px;transform:rotate(12deg);margin-right:9px}
.top-location{font-size:.75rem;color:var(--muted);margin:.3rem 0 0 23px}
.profile-pill{display:inline-flex;align-items:center;gap:7px;background:#e8f0e9;color:var(--green);border:1px solid #d8e6d9;border-radius:999px;padding:9px 14px;font-size:.82rem;font-weight:700;white-space:nowrap}
.profile-pill:before{content:"";width:7px;height:7px;background:#5c9b70;border-radius:50%;box-shadow:0 0 0 3px #d1e6d5}
div[data-testid="stButton"] button{border:1px solid transparent!important;border-radius:999px!important;background:transparent!important;color:#68756e!important;font-weight:700!important;box-shadow:none!important;min-height:2.55rem;transition:all .22s ease!important}
div[data-testid="stButton"] button:hover{background:#e9eee8!important;color:var(--ink)!important;border-color:#dfe7df!important;transform:translateY(-1px)}
div[data-testid="stButton"] button[kind="primary"]{background:var(--green)!important;color:#fff!important;border-color:var(--green)!important;box-shadow:0 7px 18px rgba(36,92,73,.16)!important}
div[data-testid="stButton"] button[kind="primary"]:hover{background:#194b3a!important;box-shadow:0 10px 24px rgba(36,92,73,.24)!important}
[data-testid="stMetric"]{background:var(--card);border:1px solid var(--line);border-radius:20px;padding:17px 20px;box-shadow:0 5px 18px rgba(25,50,37,.035)}
[data-testid="stMetricLabel"]{color:var(--muted)!important;font-weight:600}[data-testid="stMetricValue"]{font-family:'Manrope',sans-serif;font-weight:800;color:var(--green)!important;letter-spacing:-.05em}
[data-testid="stVerticalBlockBorderWrapper"]{background:var(--card);border-radius:22px;border-color:var(--line);box-shadow:0 8px 28px rgba(25,50,37,.035)}
[data-testid="stDataFrame"]{border:1px solid var(--line);border-radius:16px;overflow:hidden;background:#fff}
.stProgress>div>div>div>div{background:var(--green)}.stProgress>div>div{background:#e8eee7;border-radius:99px}
[data-testid="stExpander"]{border:1px solid var(--line);border-radius:16px;background:rgba(255,255,255,.65)}
[data-testid="stSelectbox"] [data-baseweb="select"]>div,[data-testid="stMultiSelect"] [data-baseweb="select"]>div{border-radius:12px;border-color:var(--line);background:#fff}
[data-testid="stForm"]{border:0!important}[data-testid="stAlert"]{border-radius:14px}
.stLinkButton a{border-radius:999px!important;min-height:2.6rem;font-weight:700;border-color:var(--line)!important}
.map-heading{font-family:'Manrope',sans-serif;font-size:1.55rem;font-weight:800;letter-spacing:-.055em;margin:0 0 .8rem;color:var(--ink)}
.muted-copy{color:var(--muted);font-size:.92rem}
.hero-shell{position:relative;overflow:hidden;min-height:450px;padding:3.2rem 3rem;border-radius:30px;background:linear-gradient(125deg,#173f32 0%,#245c49 58%,#39785b 100%);color:#fff;display:flex;flex-direction:column;justify-content:center;box-shadow:0 24px 60px rgba(25,67,49,.18)}
.hero-shell:before{content:"";position:absolute;width:440px;height:440px;right:-90px;top:-150px;border:1px solid rgba(255,255,255,.15);border-radius:50%;box-shadow:0 0 0 45px rgba(255,255,255,.035),0 0 0 95px rgba(255,255,255,.025)}
.hero-shell:after{content:"";position:absolute;width:170px;height:170px;right:95px;bottom:-95px;background:var(--lime);border-radius:38px;transform:rotate(28deg);opacity:.95}
.hero-kicker{font-size:.75rem;text-transform:uppercase;letter-spacing:.16em;color:#c8e0cb;font-weight:800;margin-bottom:1rem}
.hero-title{font-family:'Manrope',sans-serif;position:relative;z-index:1;font-size:clamp(2.5rem,5vw,4.6rem);font-weight:800;line-height:1.02;letter-spacing:-.075em;color:#fff;margin:0 0 1.2rem}
.hero-subtitle{position:relative;z-index:1;max-width:590px;font-size:1.08rem;line-height:1.7;color:rgba(255,255,255,.78);margin-bottom:1.5rem}
.hero-tag{position:relative;z-index:1;display:inline-flex;width:max-content;padding:9px 13px;border:1px solid rgba(255,255,255,.25);border-radius:999px;color:#e5f0df;font-size:.78rem;font-weight:700}
.login-panel{padding:.5rem .2rem}.login-heading{font-family:'Manrope',sans-serif;font-size:1.8rem;font-weight:800;letter-spacing:-.06em;margin-bottom:.3rem}
.section-eyebrow{font-size:.72rem;font-weight:800;letter-spacing:.14em;text-transform:uppercase;color:#7c8c80}
.page-intro{padding:.5rem 0 1.2rem}.page-intro h2{margin:.25rem 0 .35rem}.page-intro p{color:var(--muted);margin:0}
.nav-active button{background:#e7eee6!important;color:var(--green)!important}
@keyframes mesto-rise{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
.block-container [data-testid="stVerticalBlock"]{animation:mesto-rise .42s cubic-bezier(.2,.7,.2,1) both}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation-duration:.01ms!important;transition-duration:.01ms!important}.block-container [data-testid="stVerticalBlock"]{animation:none}}
@media(max-width:900px){.block-container{padding:.9rem .85rem 2rem}.hero-shell{min-height:360px;padding:2rem 1.5rem;border-radius:22px}.hero-title{font-size:2.55rem}.top-brand{font-size:1.5rem}}
</style>
""", unsafe_allow_html=True)

PROFILES = {
    "Студент": {"transport": 25, "education": 25, "medical": 10, "green": 10, "daily": 20, "leisure": 10},
    "Пара": {"transport": 20, "education": 5, "medical": 10, "green": 20, "daily": 20, "leisure": 25},
    "Семья с детьми": {"transport": 15, "education": 25, "medical": 20, "green": 20, "daily": 10, "leisure": 10},
}


def prepare_scores(raw_data, weights):
    """Подготовить оценки критериев и рассчитать индекс с текущими весами."""
    data = raw_data.copy()
    for key in CRITERIA:
        data[key] = data[f"score_{key}"]
    data["comfort_index"] = data.apply(
        lambda row: calculate_index(row, weights), axis=1
    )
    return data.sort_values("comfort_index", ascending=False).reset_index(drop=True)


def score_color(value, color_map):
    if pd.isna(value):
        return "#9ca3af"
    return color_map(float(value))


@st.cache_data(show_spinner=False, ttl=3600)
def load_street_segments(streets_signature=None):
    """Загрузить локальный слой улиц, подготовленный отдельным OSM-скриптом."""
    path = Path("data/raw/streets_osm.geojson")
    if not path.exists():
        return None
    try:
        streets = gpd.read_file(path)
        if streets.crs is None:
            streets = streets.set_crs("EPSG:4326")
        return streets.to_crs("EPSG:32640")
    except Exception:
        return None


def assign_cluster_street_names(clusters, streets):
    """Назначить территории название любой подходящей улицы из OSM."""
    if clusters.empty:
        return clusters

    named_streets = (
        streets[
            streets["name"].notna()
            & streets["name"].astype(str).str.strip().ne("")
        ].copy()
        if streets is not None and not streets.empty and "name" in streets.columns
        else None
    )

    display_names = []
    for row in clusters.itertuples():
        display_name = "Улица не определена по OSM"

        if named_streets is not None and not named_streets.empty:
            footprint = gpd.GeoSeries(
                [row.footprint], crs="EPSG:4326"
            ).to_crs("EPSG:32640").iloc[0]

            # Берём первую попавшуюся именованную улицу внутри контура.
            candidates = named_streets[
                named_streets.geometry.intersects(footprint)
            ]

            if not candidates.empty:
                display_name = str(candidates.iloc[0]["name"]).strip()
            else:
                # Если внутри контура улиц нет, показываем ближайшую как ориентир.
                distances = named_streets.geometry.distance(footprint)
                nearest_index = distances.idxmin()
                nearest_name = str(named_streets.loc[nearest_index, "name"]).strip()
                display_name = f"Рядом с улицей {nearest_name}"

        display_names.append(display_name)

    result = clusters.copy()
    result["display_name"] = display_names
    return result

def build_cell_clusters(frame, max_score_gap=10.0, max_cells=8):
    """Объединить соседние ячейки с ограничением диапазона оценок и размера группы."""
    projected = frame.to_crs("EPSG:32640").reset_index(drop=True)
    geometries = projected.geometry
    scores = projected["comfort_index"].astype(float).tolist()
    spatial_index = projected.sindex
    visited = set()
    clusters = []

    for seed in sorted(range(len(projected)), key=lambda i: scores[i], reverse=True):
        if seed in visited or pd.isna(scores[seed]):
            continue

        members = [seed]
        visited.add(seed)
        pending = [seed]
        min_score = max_score = scores[seed]

        while pending and len(members) < max_cells:
            current = pending.pop()
            try:
                candidates = spatial_index.query(
                    geometries.iloc[current], predicate="touches"
                )
            except TypeError:
                candidates = spatial_index.intersection(
                    geometries.iloc[current].bounds
                )

            for candidate in candidates:
                candidate = int(candidate)
                if candidate in visited or pd.isna(scores[candidate]):
                    continue
                if not geometries.iloc[current].touches(geometries.iloc[candidate]):
                    continue

                proposed_min = min(min_score, scores[candidate])
                proposed_max = max(max_score, scores[candidate])
                if proposed_max - proposed_min <= max_score_gap:
                    visited.add(candidate)
                    members.append(candidate)
                    pending.append(candidate)
                    min_score, max_score = proposed_min, proposed_max

        group = projected.iloc[members].copy()
        footprint_projected = group.geometry.unary_union
        center_projected = footprint_projected.centroid
        footprint = gpd.GeoSeries(
            [footprint_projected], crs=projected.crs
        ).to_crs("EPSG:4326").iloc[0]
        center = footprint.centroid
        clusters.append({
            "cluster_id": len(clusters),
            "cell_ids": group["cell_id"].astype(str).tolist(),
            "representative_cell": group.loc[group["comfort_index"].idxmax(), "cell_id"],
            "cell_count": len(group),
            "comfort_index": float(group["comfort_index"].mean()),
            "score_min": float(group["comfort_index"].min()),
            "score_max": float(group["comfort_index"].max()),
            "geometry": center,
            "footprint": footprint,
            **{
                f"score_{key}": group[f"score_{key}"].mean()
                for key in CRITERIA
            },
            **{
                f"nearest_distance_{key}_m": group[f"nearest_distance_{key}_m"].mean()
                for key in CRITERIA
            },
        })

    return pd.DataFrame(clusters)


def _file_signature(path):
    """Короткий ключ для сброса кэша при обновлении исходного файла."""
    file_path = Path(path)
    if not file_path.exists():
        return (str(file_path), None, None)
    stat = file_path.stat()
    return (str(file_path), stat.st_mtime_ns, stat.st_size)


@st.cache_data(show_spinner=False)
def get_profile_scores(profile_name, data_signature):
    """Рассчитать оценки один раз на профиль и версию исходных данных."""
    raw = load_real_scores()
    return prepare_scores(raw, PROFILES[profile_name])


@st.cache_data(show_spinner=False)
def get_profile_clusters(profile_name, data_signature, streets_signature, threshold_values):
    """Общий набор кластеров для карты, рейтинга и сравнения."""
    weights_data = get_profile_scores(profile_name, data_signature)
    filtered = weights_data
    for key, minimum_score in threshold_values:
        if minimum_score > 0:
            filtered = filtered[
                filtered[f"score_{key}"].notna()
                & (filtered[f"score_{key}"] >= minimum_score)
            ].copy()

    clusters = build_cell_clusters(filtered, max_score_gap=10.0)
    streets = load_street_segments(streets_signature)
    return assign_cluster_street_names(clusters, streets)


# ---------- Начальное состояние ----------
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user_email" not in st.session_state:
    st.session_state.user_email = ""
if "user_profile" not in st.session_state:
    st.session_state.user_profile = "Студент"

# ---------- Экран входа ----------
if not st.session_state.authenticated:
    st.markdown('<style>.block-container{max-width:1320px;padding-top:2.2rem;padding-bottom:3rem;}</style>', unsafe_allow_html=True)

    left, right = st.columns([1.2, 0.8], gap="large", vertical_alignment="center")
    with left:
        st.markdown(
            '<div class="hero-shell"><div class="hero-kicker">MESTO · ГОРОДСКАЯ СРЕДА</div>'
            '<div class="hero-title">Город ближе.<br>Жизнь удобнее.</div>'
            '<div class="hero-subtitle">Найдите жилую территорию Магнитогорска, '
            'которая совпадает с вашим ритмом жизни. Сравнивайте инфраструктуру '
            'не по ощущениям, а по данным.</div>'
            '<div class="hero-tag">250 × 250 м · интерактивная карта</div></div>',
            unsafe_allow_html=True,
        )
    with right:
        st.markdown(
            '<div class="login-panel"><div class="section-eyebrow">ВАШ ГОРОДСКОЙ СЦЕНАРИЙ</div>'
            '<div class="login-heading">Добро пожаловать в Mesto</div></div>',
            unsafe_allow_html=True,
        )
        st.write("Выберите приоритеты — мы настроим рекомендации под ваш образ жизни.")
        with st.form("login_form"):
            profile = st.radio(
                "Какой сценарий вам ближе?",
                options=list(PROFILES),
                captions=[
                    "Учёба, транспорт и повседневные расходы",
                    "Отдых, кафе и городская жизнь",
                    "Школы, медицина и зелёные зоны",
                ],
            )
            email = st.text_input("Электронная почта", placeholder="name@example.com")
            submitted = st.form_submit_button("Продолжить", type="primary", use_container_width=True)
            if submitted:
                email = email.strip()
                if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
                    st.error("Введите корректный адрес электронной почты.")
                else:
                    st.session_state.user_email = email
                    st.session_state.user_profile = profile
                    st.session_state.authenticated = True
                    for key in CRITERIA:
                        st.session_state.pop(f"weight_{key}", None)
                    st.rerun()
    st.stop()

# ---------- Основное приложение ----------
profile = st.session_state.user_profile

if "main_page" not in st.session_state:
    st.session_state["main_page"] = "Карта"

brand_col, nav_col, account_col = st.columns([1.15, 3.2, 1.35], vertical_alignment="center")
with brand_col:
    st.markdown('<div class="top-brand">Mesto</div><div class="top-location">Магнитогорск</div>', unsafe_allow_html=True)
with nav_col:
    nav_items = ["Карта", "Рейтинг", "Сравнение", "О проекте"]
    nav_cols = st.columns(4, gap="small")
    for nav_index, nav_item in enumerate(nav_items):
        with nav_cols[nav_index]:
            active_class = "nav-active" if st.session_state["main_page"] == nav_item else ""
            st.markdown(f'<div class="nav-button {active_class}">', unsafe_allow_html=True)
            if st.button(nav_item, key=f"nav_{nav_index}", use_container_width=True):
                st.session_state["main_page"] = nav_item
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
with account_col:
    account_left, account_right = st.columns([3, 1])
    with account_left:
        st.markdown(f'<div class="profile-pill">{profile}</div>', unsafe_allow_html=True)
    with account_right:
        if st.button("Выйти", key="logout_top", help=st.session_state.user_email):
            st.session_state.authenticated = False
            st.session_state.user_email = ""
            st.rerun()

st.divider()

page = st.session_state["main_page"]
page_descriptions = {
    "Карта": ("ИССЛЕДУЙТЕ ГОРОД", "Карта жилых территорий", "Найдите комфортные места на карте и изучите инфраструктуру вокруг них."),
    "Рейтинг": ("РЕЙТИНГ", "Территории с высоким индексом", "Изучите лидеров для жизненного сценария «" + profile.lower() + "»."),
    "Сравнение": ("СРАВНЕНИЕ", "Сопоставьте территории", "Посмотрите, где сильнее транспорт, медицина, зелёные зоны и повседневные сервисы."),
    "О проекте": ("МЕТОДОЛОГИЯ", "Как работает Mesto", "Данные, критерии и ограничения индекса городской комфортности."),
}
eyebrow, page_title, page_subtitle = page_descriptions[page]
st.markdown(
    f'<div class="page-intro"><div class="section-eyebrow">{eyebrow}</div>'
    f'<h2>{page_title}</h2><p>{page_subtitle}</p></div>',
    unsafe_allow_html=True,
)
thresholds = {key: 0 for key in CRITERIA}
if page == "Карта":
    with st.expander("Фильтры по инфраструктуре", expanded=False):
        st.caption("Укажите минимальную оценку по критериям. На карте останутся только ячейки, которые соответствуют всем заданным порогам.")
        filter_columns = st.columns(3)
        for index, (key, label) in enumerate(CRITERIA.items()):
            with filter_columns[index % 3]:
                thresholds[key] = st.slider(
                    f"{label} — минимум", min_value=0, max_value=100,
                    value=0, step=5, key=f"filter_{key}"
                )

weights = PROFILES[profile]
data_signature = (
    _file_signature("data/processed/grid_cells.geojson"),
    _file_signature("data/processed/residential_comfort_scores.csv"),
)
streets_signature = _file_signature("data/raw/streets_osm.geojson")

diagnostic_started = time.perf_counter()
try:
    data = get_profile_scores(profile, data_signature)
    logging.info(
        "MESTO_PERF data_and_scores_seconds=%.3f rows=%s",
        time.perf_counter() - diagnostic_started, len(data)
    )
except (FileNotFoundError, ValueError, OSError) as error:
    st.error("Не удалось загрузить данные городской среды. Попробуйте обновить страницу.")
    import logging
    logging.exception("Ошибка загрузки исходных геоданных: %s", error)
    st.stop()
except Exception:
    import logging
    logging.exception("Ошибка подготовки оценок жилых территорий")
    st.error("Не удалось подготовить данные для отображения. Попробуйте обновить страницу.")
    st.stop()

if data.empty:
    st.warning("Пока нет данных о жилых территориях для отображения.")
    st.stop()

threshold_values = tuple(
    (key, thresholds[key] if page == "Карта" else 0)
    for key in CRITERIA
)

# Страницы приложения
if page == "Карта":
    map_col, details_col = st.columns([1.65, 1], gap="medium")
    with map_col:
        st.markdown('<div class="map-heading">Карта жилых территорий</div>', unsafe_allow_html=True)
        color_map = LinearColormap(
            colors=["#e76f51", "#f4c95d", "#65b978"], vmin=0, vmax=100
        )
        city_map = folium.Map(
            location=[53.42, 58.98],
            zoom_start=12,
            tiles=None,
            control_scale=True,
        )
        city_map.get_root().header.add_child(folium.Element("""
        <style>
        .leaflet-control-attribution .leaflet-attribution-flag {
            display: none !important;
        }
        </style>
        """))
        # Яндекс Tiles API — основная подложка, если ключ добавлен в Streamlit Secrets.
        try:
            yandex_api_key = str(st.secrets.get("YANDEX_MAPS_API_KEY", "")).strip()
        except Exception:
            yandex_api_key = ""

        if yandex_api_key:
            yandex_tiles_url = (
                "https://tiles.api-maps.yandex.ru/v1/tiles/"
                "?x={x}&y={y}&z={z}&lang=ru_RU&l=map"
                "&projection=web_mercator&apikey=" + quote_plus(yandex_api_key)
            )
            folium.TileLayer(
                tiles=yandex_tiles_url,
                name="Яндекс",
                attr='<a href="https://yandex.ru/maps/" target="_blank">Яндекс Карты</a>',
                control=True,
                show=True,
                max_zoom=20,
                tile_size=256,
            ).add_to(city_map)

            # По условиям Tiles API логотип Яндекса должен быть виден на карте
            # и вести на главную страницу Яндекс Карт.
            city_map.get_root().html.add_child(folium.Element("""
            <a href="https://yandex.ru/maps/" target="_blank"
               style="position:absolute;bottom:14px;left:14px;z-index:1000;
                      display:block;padding:5px 9px;background:rgba(255,255,255,.94);
                      border-radius:5px;text-decoration:none;color:#222;
                      font:700 15px Arial,sans-serif;box-shadow:0 1px 4px #777;">
                Яндекс <span style="font-size:11px;font-weight:400;">Карты</span>
            </a>
            """))
        else:
            st.warning(
                "Ключ Яндекс Карт не найден в Secrets. Используется OpenStreetMap."
            )

        folium.TileLayer(
            tiles="https://tile.openstreetmap.org/{z}/{x}/{y}.png",
            name="OpenStreetMap",
            attr="© OpenStreetMap contributors",
            control=True,
            show=not bool(yandex_api_key),
            max_zoom=19,
        ).add_to(city_map)
        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            name="Спутник Esri",
            attr="Tiles © Esri",
            control=True,
            show=False,
        ).add_to(city_map)

        try:
            cluster_started = time.perf_counter()
            cluster_data = get_profile_clusters(
                profile, data_signature, streets_signature, threshold_values
            )
            logging.info(
                "MESTO_PERF clusters_and_street_names_seconds=%.3f clusters=%s",
                time.perf_counter() - cluster_started, len(cluster_data)
            )
        except Exception:
            import logging
            logging.exception("Ошибка при построении кластеров карты")
            st.error("Не удалось построить карту территорий. Попробуйте обновить страницу. Если проблема повторится, сообщите команде Mesto.")
            st.stop()

        # Переход из рейтинга к территории: находим её актуальную группу
        # с учётом включённых на карте фильтров.
        pending_cell = st.session_state.pop("selected_cell_to_show", None)
        if pending_cell is not None and not cluster_data.empty:
            matching = cluster_data[
                cluster_data["cell_ids"].apply(
                    lambda ids: str(pending_cell) in ids
                )
            ]
            if not matching.empty:
                st.session_state["selected_cluster"] = int(
                    matching.iloc[0]["cluster_id"]
                )

        cluster_labels = {
            int(row.cluster_id): (
                f"{row.display_name} · {int(row.cell_count)} яч. · "
                f"индекс {row.comfort_index:.1f}"
            )
            for row in cluster_data.itertuples()
        }
        if not cluster_data.empty:
            cluster_data["color"] = cluster_data["comfort_index"].apply(
                lambda value: score_color(value, color_map)
            )
            for row in cluster_data.itertuples():
                point = row.geometry
                radius = min(22, 7 + 2.2 * (max(1, row.cell_count) ** 0.5))
                popup_text = (
                    f"{cluster_labels[int(row.cluster_id)]}<br>"
                    f"Диапазон индексов: {row.score_min:.1f}–{row.score_max:.1f}<br>"
                    f"Нажмите, чтобы посмотреть показатели"
                )
                folium.CircleMarker(
                    location=[point.y, point.x],
                    radius=9,
                    color="#ffffff",
                    weight=1.5,
                    fill=True,
                    fill_color=row.color,
                    fill_opacity=0.88,
                    popup=folium.Popup(popup_text, max_width=280),
                    tooltip=cluster_labels[int(row.cluster_id)],
                ).add_to(city_map)

                feature = {
                    "type": "Feature",
                    "properties": {"cluster_label": cluster_labels[int(row.cluster_id)]},
                    "geometry": mapping(row.footprint),
                }
                folium.GeoJson(
                    feature,
                    style_function=lambda f, color=row.color: {
                        "color": color, "weight": 0, "opacity": 0,
                        "fillColor": color, "fillOpacity": 0.001,
                    },
                    highlight_function=lambda f, color=row.color: {
                        "color": "#20242b", "weight": 3,
                        "fillColor": color, "fillOpacity": 0.38,
                    },
                    tooltip=folium.GeoJsonTooltip(
                        fields=["cluster_label"], aliases=["Территория:"], sticky=False
                    ),
                    popup=folium.Popup(popup_text, max_width=280),
                ).add_to(city_map)

        color_map.caption = "Средний индекс комфорта"
        color_map.add_to(city_map)
        folium.LayerControl(collapsed=True).add_to(city_map)

        if not cluster_data.empty:
            bounds = gpd.GeoSeries(
                cluster_data["footprint"], crs="EPSG:4326"
            ).total_bounds
        else:
            bounds = data.total_bounds
        city_map.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])
        map_render_started = time.perf_counter()
        map_result = st_folium(
            city_map,
            use_container_width=True,
            height=720,
            key="clustered_comfort_map",
            returned_objects=["last_object_clicked", "last_object_clicked_popup"],
        )
        logging.info(
            "MESTO_PERF folium_render_seconds=%.3f",
            time.perf_counter() - map_render_started
        )

        # Сначала определяем выбранную группу по содержимому popup.
        clicked_popup = map_result.get("last_object_clicked_popup")
        selected_from_popup = False
        if clicked_popup:
            for cluster_id, label in cluster_labels.items():
                if label in str(clicked_popup):
                    st.session_state["selected_cluster"] = cluster_id
                    selected_from_popup = True
                    break

        # Если popup не вернулся (например, при клике по полигону),
        # выбираем ближайшую к точке клика группу.
        clicked_point = map_result.get("last_object_clicked")
        if not selected_from_popup and clicked_point and not cluster_data.empty:
            click_lat = clicked_point.get("lat")
            click_lon = clicked_point.get("lng")
            if click_lat is not None and click_lon is not None:
                distances = cluster_data["geometry"].apply(
                    lambda point: (point.y - click_lat) ** 2
                    + (point.x - click_lon) ** 2
                )
                st.session_state["selected_cluster"] = int(distances.idxmin())

        st.caption(
            "Круг — одна ячейка или группа соседних ячеек. "
            "В одну группу попадает не более 8 соседних ячеек с диапазоном индексов не более 10 баллов."
        )

    with details_col:
        st.subheader("Территория")
        if cluster_data.empty:
            st.warning("По заданным порогам ячейки не найдены. Уменьшите минимальные оценки фильтров.")
        else:
            cluster_options = list(cluster_labels)
            default_cluster = st.session_state.get("selected_cluster", cluster_options[0])
            if default_cluster not in cluster_options:
                default_cluster = cluster_options[0]
            selected_cluster_id = st.selectbox(
                "Выберите круг на карте или группу",
                options=cluster_options,
                index=cluster_options.index(default_cluster),
                format_func=lambda value: cluster_labels[value],
            )
            st.session_state["selected_cluster"] = selected_cluster_id
            selected_group = cluster_data.loc[
                cluster_data["cluster_id"] == selected_cluster_id
            ].iloc[0]

            st.markdown("### Индекс комфорта")
            st.metric(
                "Средняя оценка группы",
                f"{selected_group['comfort_index']:.1f} / 100",
            )
            st.caption(
                f"{int(selected_group['cell_count'])} ячеек · "
                f"разброс индексов {selected_group['score_min']:.1f}–"
                f"{selected_group['score_max']:.1f}"
            )

            criterion_values = pd.DataFrame({
                "Критерий": [CRITERIA[key] for key in CRITERIA],
                "Оценка": [selected_group[f"score_{key}"] for key in CRITERIA],
                "Среднее расстояние, м": [
                    selected_group[f"nearest_distance_{key}_m"] for key in CRITERIA
                ],
            })
            st.dataframe(
                criterion_values.round(1),
                hide_index=True,
                use_container_width=True,
            )

            point = selected_group["geometry"]
            location_query = f"Магнитогорск аренда квартиры {point.y:.5f} {point.x:.5f}"
            st.markdown("### Квартиры поблизости")
            st.caption("Откроется поиск объявлений по Магнитогорску. Точное совпадение с контуром группы пока не поддерживается.")
            link_col1, link_col2 = st.columns(2)
            with link_col1:
                st.link_button(
                    "ЦИАН · Магнитогорск ↗",
                    "https://chelyabinsk.cian.ru/snyat-kvartiru-chelyabinskaya-oblast-magnitogorsk/",
                    use_container_width=True,
                )
            with link_col2:
                st.link_button(
                    "Авито · Недвижимость ↗",
                    "https://www.avito.ru/real_estate",
                    use_container_width=True,
                )
            st.link_button(
                "Открыть расположение на карте ↗",
                f"https://yandex.ru/maps/?ll={point.x:.6f}%2C{point.y:.6f}&z=16",
                use_container_width=True,
            )

elif page == "Рейтинг":
    ranking = get_profile_clusters(
        profile, data_signature, streets_signature, threshold_values
    ).sort_values("comfort_index", ascending=False).reset_index(drop=True)
    st.subheader("Рейтинг территорий")
    st.caption("Лучшие жилые территории по выбранным приоритетам")
    for position, row in ranking.head(15).iterrows():
        with st.container(border=True):
            rank_col, score_col = st.columns([4, 1])
            with rank_col:
                st.markdown(f"**{position + 1}. {row['display_name']}**")
                st.caption(f"{int(row['cell_count'])} ячеек")
                st.progress(max(0.0, min(float(row["comfort_index"]) / 100, 1.0)))
            with score_col:
                st.metric("Индекс", f"{row['comfort_index']:.1f}")
            if st.button("Открыть на карте", key=f"show_cluster_{row['cluster_id']}"):
                st.session_state["selected_cell_to_show"] = str(row["representative_cell"])
                st.session_state["main_page"] = "Карта"
                st.rerun()

elif page == "Сравнение":
    comparison_clusters = get_profile_clusters(
        profile, data_signature, streets_signature, threshold_values
    ).sort_values("comfort_index", ascending=False).reset_index(drop=True)
    st.subheader("Сравнение территорий")
    cluster_ids = comparison_clusters["cluster_id"].astype(int).tolist()
    selected_clusters = st.multiselect(
        "Выберите две или три территории",
        options=cluster_ids,
        default=cluster_ids[:2],
        format_func=lambda value: comparison_clusters.loc[
            comparison_clusters["cluster_id"] == value, "display_name"
        ].iloc[0],
        max_selections=3,
    )
    if selected_clusters:
        comparison = comparison_clusters[
            comparison_clusters["cluster_id"].isin(selected_clusters)
        ].copy()
        comparison["Территория"] = comparison.apply(
            lambda row: f"{row['display_name']} · {int(row['cell_count'])} яч.",
            axis=1,
        )
        display_columns = [
            "Территория", "comfort_index",
            *[f"score_{key}" for key in CRITERIA]
        ]
        display = comparison[display_columns].rename(
            columns={
                "comfort_index": "Индекс комфорта",
                **{f"score_{key}": label for key, label in CRITERIA.items()},
            }
        )
        st.dataframe(display.round(1), hide_index=True, use_container_width=True)
        chart_data = comparison.melt(
            id_vars=["Территория"],
            value_vars=[f"score_{key}" for key in CRITERIA],
            var_name="criterion",
            value_name="score",
        )
        chart_data["criterion"] = chart_data["criterion"].map(
            {f"score_{key}": label for key, label in CRITERIA.items()}
        )
        fig = px.bar(
            chart_data, x="criterion", y="score", color="Территория",
            barmode="group", range_y=[0, 100],
            labels={"criterion": "Критерий", "score": "Оценка", "Территория": "Территория"},
        )
        st.plotly_chart(fig, use_container_width=True)

elif page == "О проекте":
    st.subheader("О проекте")
    st.markdown(
        """
        Mesto помогает сравнивать жилые территории по доступности городской инфраструктуры
        с учётом жизненного сценария.

        **Как работает индекс:** оценки шести категорий объединяются с весами профиля.
        Если по критерию нет наблюдения, его вес исключается, а остальные веса нормализуются.

        **Ограничения:** OSM может быть неполным; доступность пока измеряется прямолинейным
        расстоянием от центра ячейки, а не временем пешего маршрута. Порог P90 —
        статистический, а не нормативный.
        """
    )
    st.subheader("Приоритеты профиля")
    st.dataframe(
        pd.DataFrame({
            "Критерий": [CRITERIA[key] for key in CRITERIA],
            "Вес": [weights[key] for key in CRITERIA],
        }),
        hide_index=True,
        use_container_width=True,
    )

st.caption("Учебный проект · Индекс комфорта городской среды · Магнитогорск")

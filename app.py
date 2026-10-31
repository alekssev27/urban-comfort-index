import re
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
#MainMenu, footer {visibility: hidden;}
[data-testid="stSidebar"] {display: none;}
.block-container {max-width: 1900px; padding: 1.25rem 2.2rem 2rem;}
header[data-testid="stHeader"] {background:#fff !important; height:3.25rem; visibility:visible;}
.top-brand {font-size: 1.65rem; font-weight: 800; letter-spacing: -.06em; color: #20242b; padding-top: .35rem;}
.top-location {font-size: .82rem; color: #8a9099; margin-top: -.25rem;}
.profile-pill {display:inline-block; background:#f1f5f2; color:#397b54; border-radius:999px; padding:9px 15px; font-size:.9rem; font-weight:600;}
div[data-testid="stButton"] button {position:relative;background:transparent !important;border:0 !important;border-radius:0 !important;color:#343943 !important;font-weight:600;box-shadow:none !important;padding:.55rem .35rem .8rem !important;}
div[data-testid="stButton"] button:after {content:"";position:absolute;left:0;right:0;bottom:0;height:2px;background:#252a33;transform:scaleX(0);transition:transform .18s ease;}
div[data-testid="stButton"] button:hover:after {transform:scaleX(1);}
h1,h2,h3 {letter-spacing:-.045em; color:#252a33;}
[data-testid="stMetric"] {background:#fff; border:1px solid #e9edf1; border-radius:18px; padding:16px 18px;}
[data-testid="stVerticalBlockBorderWrapper"] {border-radius:18px; border-color:#e9edf1;}
.stButton button, .stLinkButton a {border-radius:12px; min-height:2.65rem;}
[data-testid="stDataFrame"] {border:1px solid #edf0f2; border-radius:12px; overflow:hidden;}
.map-heading {font-size:1.45rem; font-weight:750; letter-spacing:-.04em; margin-bottom:.65rem;}
.muted-copy {color:#858b94; font-size:.92rem;}
@media (max-width: 900px) {
 .block-container {padding:1rem .8rem;}
}
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


def load_street_segments():
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
    """Выбрать улицу с наибольшей длиной внутри каждой группы."""
    if clusters.empty:
        return clusters
    used_names = {}
    display_names = []
    for row in clusters.itertuples():
        best_name = None
        if streets is not None and not streets.empty:
            footprint = gpd.GeoSeries(
                [row.footprint], crs="EPSG:4326"
            ).to_crs("EPSG:32640").iloc[0]
            candidates = streets[streets.geometry.intersects(footprint)]
            lengths = {}
            for street in candidates.itertuples():
                name = getattr(street, "name", None)
                if not name or pd.isna(name):
                    continue
                clipped = street.geometry.intersection(footprint)
                if not clipped.is_empty:
                    lengths[name] = lengths.get(name, 0.0) + clipped.length
            if lengths:
                best_name = max(lengths, key=lengths.get)

        best_name = best_name or "Жилая территория"
        used_names[best_name] = used_names.get(best_name, 0) + 1
        suffix = used_names[best_name]
        display_names.append(
            best_name if suffix == 1 else f"{best_name} {suffix}"
        )

    result = clusters.copy()
    result["display_name"] = display_names
    return result


def build_cell_clusters(frame, max_score_gap=10.0):
    """Объединить только соседние ячейки, диапазон индексов которых <= max_score_gap."""
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

        while pending:
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


# ---------- Начальное состояние ----------
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user_email" not in st.session_state:
    st.session_state.user_email = ""
if "user_profile" not in st.session_state:
    st.session_state.user_profile = "Студент"

# ---------- Экран входа ----------
if not st.session_state.authenticated:
    st.markdown(
        """
        <style>
        .block-container {max-width: 1050px; padding-top: 3rem; padding-bottom: 3rem;}
        .hero-title {font-size: 2.65rem; font-weight: 750; line-height: 1.15;
                     letter-spacing: -1px; margin-bottom: 1rem;}
        .hero-subtitle {font-size: 1.1rem; line-height: 1.7; color: #64748b;
                        margin-bottom: 1.5rem;}
        </style>
        """,
        unsafe_allow_html=True,
    )
    left, right = st.columns([1.15, 0.85], gap="large", vertical_alignment="center")
    with left:
        st.markdown("### Mesto")
        st.markdown(
            '<div class="hero-title">Найдите территорию,<br>которая подходит именно вам.</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="hero-subtitle">Сравнивайте жилые ячейки Магнитогорска '
            'по доступности транспорта, образования, медицины, зелёных зон, '
            'повседневной инфраструктуры и досуга.</div>',
            unsafe_allow_html=True,
        )
        st.markdown("**Что вы получите:**")
        st.markdown(
            "- Персональный рейтинг жилых ячеек.\n"
            "- Интерактивную карту реальных географических ячеек.\n"
            "- Сравнение территорий по шести критериям."
        )
        st.caption("Учебный прототип · Магнитогорск")
    with right:
        with st.container(border=True):
            st.subheader("Добро пожаловать")
            st.write("Выберите жизненный сценарий для настройки рекомендаций.")
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
                submitted = st.form_submit_button(
                    "Продолжить", type="primary", use_container_width=True
                )
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

with st.expander("Фильтры по инфраструктуре", expanded=False):
    st.caption("Укажите минимальную оценку по критериям. На карте останутся только ячейки, которые соответствуют всем заданным порогам.")
    filter_columns = st.columns(3)
    thresholds = {}
    for index, (key, label) in enumerate(CRITERIA.items()):
        with filter_columns[index % 3]:
            thresholds[key] = st.slider(f"{label} — минимум", min_value=0, max_value=100, value=0, step=5, key=f"filter_{key}")

weights = PROFILES[profile]
try:
    raw_data = load_real_scores()
except (FileNotFoundError, ValueError, OSError) as error:
    st.error(f"Не удалось загрузить реальные геоданные: {error}")
    st.info(
        "Проверьте наличие data/processed/grid_cells.geojson и "
        "data/processed/residential_comfort_scores.csv."
    )
    st.stop()

data = prepare_scores(raw_data, weights)
if data.empty:
    st.error("После объединения геоданных не осталось жилых ячеек.")
    st.stop()

filtered_data = data.copy()
for criterion, minimum_score in thresholds.items():
    if minimum_score > 0:
        filtered_data = filtered_data[
            filtered_data[f"score_{criterion}"].notna()
            & (filtered_data[f"score_{criterion}"] >= minimum_score)
        ].copy()

page = st.session_state["main_page"]

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
        folium.TileLayer(
            tiles="https://tile.openstreetmap.org/{z}/{x}/{y}.png",
            name="Карта",
            attr="© OpenStreetMap contributors",
            control=True,
            show=True,
            max_zoom=19,
        ).add_to(city_map)
        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            name="Спутник",
            attr="Tiles © Esri",
            control=True,
            show=False,
        ).add_to(city_map)

        cluster_data = build_cell_clusters(filtered_data, max_score_gap=10.0) if not filtered_data.empty else pd.DataFrame()
        cluster_data = assign_cluster_street_names(cluster_data, load_street_segments())
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
                        "color": "#20242b", "weight": 1,
                        "fillColor": color, "fillOpacity": 0.01,
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

        bounds = (filtered_data if not filtered_data.empty else data).total_bounds
        city_map.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])
        map_result = st_folium(
            city_map,
            use_container_width=True,
            height=720,
            key="clustered_comfort_map",
            returned_objects=["last_object_clicked_popup"],
        )

        clicked_popup = map_result.get("last_object_clicked_popup")
        if clicked_popup:
            for cluster_id, label in cluster_labels.items():
                if label in str(clicked_popup):
                    st.session_state["selected_cluster"] = cluster_id
                    break

        st.caption(
            "Круг — одна ячейка или группа соседних ячеек. "
            "В одну группу попадают только ячейки с диапазоном индексов не более 10 баллов."
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
    cluster_data = build_cell_clusters(filtered_data, max_score_gap=10.0) if not filtered_data.empty else pd.DataFrame()
    st.subheader("Рейтинг территорий")
    st.caption("Лучшие жилые ячейки по выбранным приоритетам")
    for position, row in filtered_data.head(15).iterrows():
        with st.container(border=True):
            rank_col, score_col = st.columns([4, 1])
            with rank_col:
                st.markdown(f"**{position + 1}. {row['cell_id']}**")
                st.progress(max(0.0, min(float(row["comfort_index"]) / 100, 1.0)))
            with score_col:
                st.metric("Индекс", f"{row['comfort_index']:.1f}")
            if st.button("Открыть на карте", key=f"show_cell_{row['cell_id']}"):
                matching = cluster_data[
                    cluster_data["cell_ids"].apply(
                        lambda ids: str(row["cell_id"]) in ids
                    )
                ]
                if not matching.empty:
                    st.session_state["selected_cluster"] = int(
                        matching.iloc[0]["cluster_id"]
                    )
                st.session_state["main_page"] = "Карта"
                st.rerun()

elif page == "Сравнение":
    st.subheader("Сравнение жилых ячеек")
    selected_cells = st.multiselect(
        "Выберите две или три ячейки",
        filtered_data["cell_id"].tolist(),
        default=filtered_data["cell_id"].tolist()[:2],
        max_selections=3,
    )
    if selected_cells:
        comparison = filtered_data[filtered_data["cell_id"].isin(selected_cells)].copy()
        display_columns = [
            "cell_id", "comfort_index", *[f"score_{key}" for key in CRITERIA]
        ]
        display = comparison[display_columns].rename(
            columns={
                "cell_id": "Ячейка",
                "comfort_index": "Индекс комфорта",
                **{f"score_{key}": label for key, label in CRITERIA.items()},
            }
        )
        st.dataframe(display.round(1), hide_index=True, use_container_width=True)
        chart_data = comparison.melt(
            id_vars=["cell_id"],
            value_vars=[f"score_{key}" for key in CRITERIA],
            var_name="criterion",
            value_name="score",
        )
        chart_data["criterion"] = chart_data["criterion"].map(
            {f"score_{key}": label for key, label in CRITERIA.items()}
        )
        fig = px.bar(
            chart_data, x="criterion", y="score", color="cell_id",
            barmode="group", range_y=[0, 100],
            labels={"criterion": "Критерий", "score": "Оценка", "cell_id": "Ячейка"},
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

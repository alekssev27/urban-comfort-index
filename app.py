import re
from urllib.parse import quote_plus

import folium
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
.block-container {padding: 1.1rem 2rem 2rem; max-width: 1800px;}
[data-testid="stSidebar"] {background: #fafafa; border-right: 1px solid #edf0f2;}
[data-testid="stMetric"] {background: #fff; border: 1px solid #edf0f2; padding: 12px 14px; border-radius: 16px;}
[data-testid="stRadio"] > div {gap: 0.35rem;}
h1, h2, h3 {letter-spacing: -0.035em;}
div[data-testid="stVerticalBlockBorderWrapper"] {border-radius: 18px;}
.stButton button, .stLinkButton a {border-radius: 12px;}
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
        center = group.geometry.union_all().centroid
        clusters.append({
            "cluster_id": len(clusters),
            "cell_ids": group["cell_id"].astype(str).tolist(),
            "representative_cell": group.loc[group["comfort_index"].idxmax(), "cell_id"],
            "cell_count": len(group),
            "comfort_index": float(group["comfort_index"].mean()),
            "score_min": float(group["comfort_index"].min()),
            "score_max": float(group["comfort_index"].max()),
            "geometry": center,
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
st.sidebar.title("Mesto")
st.sidebar.caption("Магнитогорск")
st.sidebar.success(f"Ваш профиль: {profile}")
st.sidebar.caption(st.session_state.user_email)

if st.sidebar.button("Выйти", use_container_width=True):
    st.session_state.authenticated = False
    st.session_state.user_email = ""
    for key in CRITERIA:
        st.session_state.pop(f"weight_{key}", None)
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("Настройка приоритетов")
st.sidebar.caption("Изменяйте веса критериев, чтобы настроить рейтинг под свои предпочтения.")

weights = {}
for key, label in CRITERIA.items():
    weights[key] = st.sidebar.slider(
        label,
        min_value=0,
        max_value=100,
        value=PROFILES[profile][key],
        key=f"weight_{key}",
    )

if sum(weights.values()) == 0:
    st.sidebar.warning("Укажите ненулевой вес хотя бы одного критерия.")

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

# Основная рабочая область
page = st.sidebar.radio(
    "Раздел",
    ["🗺️ Карта", "🏆 Рейтинг", "📊 Сравнение", "ℹ️ О проекте"],
    key="main_page",
)

header_col, profile_col = st.columns([4, 1])
with header_col:
    st.markdown("# Mesto")
    st.caption("Найдите территорию, которая подходит вашему образу жизни")
with profile_col:
    st.markdown(f"**{profile}**")
    st.caption("Магнитогорск")

if page == "🗺️ Карта":
    map_col, details_col = st.columns([1.65, 1], gap="medium")
    with map_col:
        st.subheader("Карта жилых территорий")
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

        cluster_data = build_cell_clusters(data, max_score_gap=10.0)
        cluster_labels = {
            int(row.cluster_id): (
                f"Группа {int(row.cluster_id) + 1} · {int(row.cell_count)} яч. · "
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
                    radius=radius,
                    color="#ffffff",
                    weight=1.5,
                    fill=True,
                    fill_color=row.color,
                    fill_opacity=0.88,
                    popup=folium.Popup(popup_text, max_width=280),
                    tooltip=cluster_labels[int(row.cluster_id)],
                ).add_to(city_map)

        color_map.caption = "Средний индекс комфорта"
        color_map.add_to(city_map)
        folium.LayerControl(collapsed=True).add_to(city_map)

        bounds = data.total_bounds
        city_map.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])
        map_result = st_folium(
            city_map,
            use_container_width=True,
            height=680,
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
            st.warning("Не удалось сформировать группы ячеек.")
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
                key="cluster_selector",
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
            location_query = (
                f"Магнитогорск {point.y:.5f} {point.x:.5f} аренда квартиры"
            )
            st.markdown("### Квартиры поблизости")
            st.caption(
                "Поиск откроется на внешней площадке. Встроенные объявления "
                "подключим после согласования официального доступа."
            )
            cian_query = quote_plus(f"site:cian.ru аренда квартиры {location_query}")
            avito_query = quote_plus(f"site:avito.ru аренда квартиры {location_query}")
            link_col1, link_col2 = st.columns(2)
            with link_col1:
                st.link_button(
                    "ЦИАН ↗",
                    f"https://www.google.com/search?q={cian_query}",
                    use_container_width=True,
                )
            with link_col2:
                st.link_button(
                    "Авито ↗",
                    f"https://www.google.com/search?q={avito_query}",
                    use_container_width=True,
                )

elif page == "🏆 Рейтинг":
    st.subheader("Рейтинг территорий")
    st.caption("Лучшие жилые ячейки по выбранным приоритетам")
    for position, row in data.head(15).iterrows():
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
                st.session_state["main_page"] = "🗺️ Карта"
                st.rerun()

elif page == "📊 Сравнение":
    st.subheader("Сравнение жилых ячеек")
    selected_cells = st.multiselect(
        "Выберите две или три ячейки",
        data["cell_id"].tolist(),
        default=data["cell_id"].tolist()[:2],
        max_selections=3,
    )
    if selected_cells:
        comparison = data[data["cell_id"].isin(selected_cells)].copy()
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

elif page == "ℹ️ О проекте":
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

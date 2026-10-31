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

st.title("Mesto")
st.write(f"Персональный анализ жилых территорий для сценария **«{profile}»**.")
st.info(
    "На карте показаны только ячейки, в которых обнаружены жилые здания в OSM. "
    "Доступность рассчитана по прямолинейному расстоянию; данные OSM могут быть неполными."
)

best = data.iloc[0]
col1, col2, col3 = st.columns(3)
col1.metric("Жилых ячеек в рейтинге", f"{len(data):,}".replace(",", " "))
col2.metric("Лучшая оценка", f"{best['comfort_index']:.1f} / 100")
col3.metric("Ваш профиль", profile)

map_tab, compare_tab, about_tab = st.tabs(
    ["🗺️ Карта и рейтинг", "📊 Сравнение", "ℹ️ О проекте"]
)

with map_tab:
    map_col, ranking_col = st.columns([1.8, 1], gap="large")
    with map_col:
        st.subheader("Карта жилых ячеек")
        color_map = LinearColormap(
            colors=["#dc2626", "#facc15", "#16a34a"], vmin=0, vmax=100
        )
        color_map.caption = "Индекс комфорта"
        city_map = folium.Map(
            location=[53.42, 58.98],
            zoom_start=12,
            tiles="CartoDB positron",
            control_scale=True,
        )
        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            name="Спутник", attr="Tiles © Esri", control=True, show=False,
        ).add_to(city_map)
        folium.LayerControl(position="topright", collapsed=True).add_to(city_map)

        map_data = data[
            ["cell_id", "comfort_index", *[f"score_{key}" for key in CRITERIA], "geometry"]
        ].copy()
        map_data["comfort_index"] = map_data["comfort_index"].round(1)

        def style_function(feature):
            value = feature["properties"].get("comfort_index")
            return {
                "fillColor": score_color(value, color_map),
                "color": "#374151",
                "weight": 0.35,
                "fillOpacity": 0.72,
            }

        folium.GeoJson(
            data=map_data.to_json(),
            name="Индекс комфорта",
            style_function=style_function,
            highlight_function=lambda feature: {
                "weight": 2, "color": "#111827", "fillOpacity": 0.9
            },
            tooltip=folium.GeoJsonTooltip(
                fields=["cell_id", "comfort_index"],
                aliases=["ID ячейки", "Индекс комфорта"],
                localize=True,
                sticky=False,
            ),
        ).add_to(city_map)
        color_map.add_to(city_map)
        folium.LayerControl().add_to(city_map)

        bounds = map_data.total_bounds
        city_map.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])
        st_folium(
            city_map,
            use_container_width=True,
            height=570,
            key="real_comfort_map",
        )
        st.caption(
            "Каждый квадрат — ячейка сетки 250 × 250 м. Цвет показывает "
            "персональный индекс комфорта."
        )

    with ranking_col:
        st.subheader("Рейтинг территорий")
        st.caption("Первые 15 ячеек по выбранным весам")
        for position, row in data.head(15).iterrows():
            with st.container(border=True):
                st.write(f"**{position + 1}. {row['cell_id']}**")
                st.progress(max(0.0, min(float(row["comfort_index"]) / 100, 1.0)))
                st.caption(f"Индекс: {row['comfort_index']:.1f} / 100")

        st.subheader("Выбранная территория")
        selected_cell = st.selectbox("Выберите ячейку по идентификатору", data["cell_id"].tolist(), key="selected_cell_details")
        selected_row = data.loc[data["cell_id"] == selected_cell].iloc[0]
        st.subheader("Показатели ячейки")
        st.metric("Индекс комфорта", f"{selected_row['comfort_index']:.1f} / 100")
        criterion_values = pd.DataFrame(
            {
                "Критерий": [CRITERIA[key] for key in CRITERIA],
                "Оценка": [selected_row[f"score_{key}"] for key in CRITERIA],
                "Расстояние до объекта, м": [
                    selected_row[f"nearest_distance_{key}_m"] for key in CRITERIA
                ],
            }
        )
        st.dataframe(criterion_values, hide_index=True, use_container_width=True)

        centroid = selected_row.geometry.centroid
        location_query = f"Магнитогорск {centroid.y:.5f} {centroid.x:.5f} аренда квартиры"
        st.markdown("#### Квартиры поблизости")
        st.caption("Пока открывается внешний поиск по координатам выбранной ячейки. Встроенные объявления подключим после согласования официального доступа к данным площадок.")
        cian_query = quote_plus(f"site:cian.ru аренда квартиры {location_query}")
        avito_query = quote_plus(f"site:avito.ru аренда квартиры {location_query}")
        link_col1, link_col2 = st.columns(2)
        with link_col1:
            st.link_button("Искать на ЦИАН ↗", f"https://www.google.com/search?q={cian_query}", use_container_width=True)
        with link_col2:
            st.link_button("Искать на Авито ↗", f"https://www.google.com/search?q={avito_query}", use_container_width=True)

with compare_tab:
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
        st.dataframe(display, hide_index=True, use_container_width=True)

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
            chart_data,
            x="criterion",
            y="score",
            color="cell_id",
            barmode="group",
            labels={
                "criterion": "Критерий",
                "score": "Оценка",
                "cell_id": "Ячейка",
            },
            range_y=[0, 100],
        )
        st.plotly_chart(fig, use_container_width=True)

with about_tab:
    st.subheader("О проекте")
    st.markdown(
        """
        Mesto помогает подбирать жильё и сравнивать жилые территории по доступности городской
        инфраструктуры с учётом жизненного сценария.

        **Как рассчитывается индекс:**
        1. Для каждой категории инфраструктуры рассчитывается оценка от 0 до 100.
        2. Оценки объединяются с весами выбранного сценария.
        3. Если по критерию нет наблюдения, его вес исключается, а остальные веса
           нормализуются.
        4. Жилые ячейки ранжируются по итоговому индексу.

        **Ограничения текущей версии:**
        - в рейтинг попадают только ячейки, где OSM обнаружил жилые здания;
        - объекты OSM могут быть неполными или устаревшими;
        - доступность пока измеряется прямолинейным расстоянием от центра ячейки,
          а не временем пешего маршрута;
        - пороги P90 являются статистическими порогами выборки, а не нормативами.
        """
    )
    st.subheader("Критерии и веса")
    st.dataframe(
        pd.DataFrame(
            {
                "Критерий": [CRITERIA[key] for key in CRITERIA],
                "Вес": [weights[key] for key in CRITERIA],
            }
        ),
        hide_index=True,
        use_container_width=True,
    )

st.caption("Учебный проект · Индекс комфорта городской среды · Магнитогорск")

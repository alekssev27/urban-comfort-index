import re

import folium
import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit_folium import st_folium

from src.data_loader import load_demo_scores
from src.scoring import CRITERIA, calculate_index

st.set_page_config(
    page_title="Индекс комфорта",
    page_icon="🏙️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------- Демонстрационные данные ----------

PROFILES = {
    "Студент": {
        "transport": 25,
        "education": 25,
        "medical": 10,
        "green": 10,
        "daily": 20,
        "leisure": 10,
    },
    "Пара": {
        "transport": 20,
        "education": 5,
        "medical": 10,
        "green": 20,
        "daily": 20,
        "leisure": 25,
    },
    "Семья с детьми": {
        "transport": 15,
        "education": 25,
        "medical": 20,
        "green": 20,
        "daily": 10,
        "leisure": 10,
    },
}



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
        .block-container {
            max-width: 1050px;
            padding-top: 3rem;
            padding-bottom: 3rem;
        }
        .hero-title {
            font-size: 2.65rem;
            font-weight: 750;
            line-height: 1.15;
            letter-spacing: -1px;
            margin-bottom: 1rem;
        }
        .hero-subtitle {
            font-size: 1.1rem;
            line-height: 1.7;
            color: #64748b;
            margin-bottom: 1.5rem;
        }
        .login-card {
            border: 1px solid rgba(128, 128, 128, 0.25);
            border-radius: 18px;
            padding: 1.5rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    left, right = st.columns(
        [1.15, 0.85],
        gap="large",
        vertical_alignment="center",
    )

    with left:
        st.markdown("### 🏙️ Индекс комфорта")

        st.markdown(
            '<div class="hero-title">'
            'Найдите район,<br>который подходит именно вам.'
            '</div>',
            unsafe_allow_html=True,
        )

        st.markdown(
            """
            <div class="hero-subtitle">
            Сравнивайте территории Магнитогорска по доступности
            транспорта, парков, образования, медицины и других
            объектов городской инфраструктуры.
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("**Что вы получите:**")
        st.markdown(
            """
            - Персональный рейтинг территорий.
            - Интерактивную карту инфраструктуры.
            - Сравнение сильных сторон разных районов.
            """
        )

        st.caption(
            "Учебный прототип · Магнитогорск"
        )

    with right:
        with st.container(border=True):
            st.subheader("Добро пожаловать")
            st.write(
                "Расскажите немного о себе, "
                "чтобы настроить рекомендации."
            )

            with st.form("login_form"):
                profile = st.radio(
                    "Какой сценарий вам ближе?",
                    options=list(PROFILES.keys()),
                    captions=[
                        "Учёба, транспорт и повседневные расходы",
                        "Отдых, кафе и городская жизнь",
                        "Школы, медицина и зелёные зоны",
                    ],
                )

                email = st.text_input(
                    "Электронная почта",
                    placeholder="name@example.com",
                )

                submitted = st.form_submit_button(
                    "Продолжить",
                    type="primary",
                    use_container_width=True,
                )

                if submitted:
                    email = email.strip()

                    valid_email = re.fullmatch(
                        r"[^@\s]+@[^@\s]+\.[^@\s]+",
                        email,
                    )

                    if not valid_email:
                        st.error(
                            "Введите корректный адрес электронной почты."
                        )
                    else:
                        st.session_state.user_email = email
                        st.session_state.user_profile = profile
                        st.session_state.authenticated = True

                        # При новом входе сбрасываем старые веса.
                        for key in CRITERIA:
                            st.session_state.pop(
                                f"weight_{key}",
                                None,
                            )

                        st.rerun()

    st.stop()


# ---------- Основное приложение ----------

profile = st.session_state.user_profile

st.sidebar.title("🏙️ Индекс комфорта")
st.sidebar.caption("Магнитогорск")

st.sidebar.success(f"Ваш профиль: {profile}")
st.sidebar.caption(st.session_state.user_email)

if st.sidebar.button(
    "Выйти",
    use_container_width=True,
):
    st.session_state.authenticated = False
    st.session_state.user_email = ""

    for key in CRITERIA:
        st.session_state.pop(f"weight_{key}", None)

    st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("Настройка приоритетов")
st.sidebar.caption(
    "Изменяйте веса критериев, чтобы настроить рейтинг "
    "под свои предпочтения."
)

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
    st.sidebar.warning(
        "Укажите ненулевой вес хотя бы одного критерия."
    )

data = load_demo_scores()

data["comfort_index"] = data.apply(
    lambda row: calculate_index(row, weights),
    axis=1,
)

data = data.sort_values(
    "comfort_index",
    ascending=False,
).reset_index(drop=True)

st.title("Карта комфорта городской среды")
st.write(
    f"Персональный анализ территорий для сценария "
    f"**«{profile}»**."
)

st.warning(
    "Демонстрационный режим: оценки и точки на карте условные. "
    "Они не являются результатами реального анализа Магнитогорска."
)

best = data.iloc[0]

col1, col2, col3 = st.columns(3)

col1.metric(
    "Территорий в прототипе",
    len(data),
)

col2.metric(
    "Лучший демонстрационный результат",
    f"{best['comfort_index']:.1f} / 100",
)

col3.metric(
    "Ваш профиль",
    profile,
)

map_tab, compare_tab, about_tab = st.tabs([
    "🗺️ Карта и рейтинг",
    "📊 Сравнение",
    "ℹ️ О проекте",
])

with map_tab:
    map_col, ranking_col = st.columns(
        [1.8, 1],
        gap="large",
    )

    with map_col:
        st.subheader("Карта территорий")

        city_map = folium.Map(
            location=[53.42, 58.98],
            zoom_start=12,
            tiles="OpenStreetMap",
        )

        for _, row in data.iterrows():
            folium.CircleMarker(
                location=[row["lat"], row["lon"]],
                radius=11,
                color="#2563eb",
                fill=True,
                fill_color="#3b82f6",
                fill_opacity=0.8,
                tooltip=(
                    f"{row['name']} · "
                    f"Индекс: {row['comfort_index']:.1f}"
                ),
                popup=(
                    f"<b>{row['name']}</b><br>"
                    f"Индекс: {row['comfort_index']:.1f}/100"
                ),
            ).add_to(city_map)

        st_folium(
            city_map,
            use_container_width=True,
            height=470,
            key="comfort_map",
        )

        st.caption(
            "Точки условные. Реальные объекты и границы "
            "будут добавлены после подготовки геоданных."
        )

    with ranking_col:
        st.subheader("Рейтинг территорий")

        for position, row in data.iterrows():
            with st.container(border=True):
                st.write(
                    f"**{position + 1}. {row['name']}**"
                )
                st.progress(
                    max(
                        0.0,
                        min(float(row["comfort_index"]) / 100, 1.0),
                    )
                )
                st.caption(
                    f"Индекс: {row['comfort_index']:.1f} / 100"
                )

        selected = st.selectbox(
            "Подробнее о территории",
            data["name"].tolist(),
        )

        selected_row = data.loc[
            data["name"] == selected
        ].iloc[0]

        st.subheader(selected)
        st.metric(
            "Индекс комфорта",
            f"{selected_row['comfort_index']:.1f} / 100",
        )

        criterion_values = pd.DataFrame({
            "Критерий": [
                CRITERIA[key] for key in CRITERIA
            ],
            "Оценка": [
                selected_row[key] for key in CRITERIA
            ],
        })

        st.dataframe(
            criterion_values,
            hide_index=True,
            use_container_width=True,
        )

with compare_tab:
    st.subheader("Сравнение территорий")

    selected_names = st.multiselect(
        "Выберите две или три территории",
        data["name"].tolist(),
        default=data["name"].tolist()[:2],
        max_selections=3,
    )

    if selected_names:
        comparison = data[
            data["name"].isin(selected_names)
        ]

        st.dataframe(
            comparison[
                ["name", "comfort_index", *CRITERIA.keys()]
            ].rename(columns={
                "name": "Территория",
                "comfort_index": "Индекс комфорта",
                **CRITERIA,
            }),
            hide_index=True,
            use_container_width=True,
        )

        chart_data = comparison.melt(
            id_vars=["name"],
            value_vars=list(CRITERIA.keys()),
            var_name="criterion",
            value_name="score",
        )

        chart_data["criterion"] = chart_data[
            "criterion"
        ].map(CRITERIA)

        fig = px.bar(
            chart_data,
            x="criterion",
            y="score",
            color="name",
            barmode="group",
            labels={
                "criterion": "Критерий",
                "score": "Оценка",
                "name": "Территория",
            },
            range_y=[0, 100],
        )

        st.plotly_chart(
            fig,
            use_container_width=True,
        )

with about_tab:
    st.subheader("О проекте")

    st.markdown("""
    Сервис помогает сравнивать территории по доступности
    городской инфраструктуры с учётом жизненного сценария.

    **Как рассчитывается индекс:**
    1. Для каждого критерия определяется оценка.
    2. Критерии получают веса в зависимости от сценария.
    3. Рассчитывается взвешенный индекс.
    4. Территории ранжируются по итоговому значению.

    Текущие данные демонстрационные. Перед использованием
    результатов в исследовании необходимо подключить
    проверенные геоданные и утвердить методику расчёта.
    """)

    st.subheader("Критерии")
    for key, label in CRITERIA.items():
        st.write(f"- {label}: вес {weights[key]}")

st.caption(
    "Учебный проект · Индекс комфорта городской среды · Магнитогорск"
)

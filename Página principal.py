import streamlit as st
import pandas as pd

st.markdown("""
    <style>
        .custom-header {
            color: #0D3E8A;  /* Azul más visible en ambos modos */
        }
        .custom-subheader {
            color: #555;  /* Gris oscuro, legible en fondo claro y fondo oscuro */
        }
        .custom-box {
            background-color: #5353ec;
            padding: 15px;
            border-radius: 10px;
            border: 1px solid #ccc;
        }
        .custom-text {
            color: #FFFFFF;
            font-size: 16px;
        }
        @media (prefers-color-scheme: dark) {
            .custom-header {
                color: #1f77b4;
            }
            .custom-subheader {
                color: #ccc;
            }
            .custom-box {
                background-color: #FB0B0E;
                border: 1px solid #444;
            }
            .custom-text {
                color: #FFFFFF;
            }
        }
    </style>

    <h1 class='custom-header'>⚽ Performance | Secretaría Técnica</h1>
    <h3 class='custom-subheader'>Reportes vía tracking de los datos físicos</h3>

    <div class='custom-box'>
        <p class='custom-text'>
            📌 <em>Detalles a tener en cuenta:</em><br><br>
            La aplicación se nutre de los datos de Skill Corner automáticamente desde una conexión a la API de la empresa, por lo que no hace falta una carga manual. La información puede demorar hasta 24 horas tras el final del partido para aparecer acá (dependemos exclusivamente de la empresa que disponibiliza los datos).
            De todas maneras, cada página tiene un botón de actualización por si hace falta realizar la consulta a la API nuevamente.
    </div>
""", unsafe_allow_html=True)


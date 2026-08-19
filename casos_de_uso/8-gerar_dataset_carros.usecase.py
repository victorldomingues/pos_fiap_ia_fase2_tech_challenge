from pathlib import Path
import pandas as pd

# 

BASE_DIR = Path(__file__).resolve().parents[1]
BASES_DIR = BASE_DIR / "bases"
CARROS_DATASET_PATH = BASES_DIR / "PBEV_2026_simplificado.csv"
NOVO_CARROS_DATASET_PATH = BASES_DIR / "Carros.csv"

# considerando apenas carros flex
df_columns = ["marca", "modelo", "versao", "combustivel", "consumo_cidade", "consumo_cidade_2", "consumo_estrada", "consumo_estrada_2", "classificacao_pbe", "classificacao_geral"]
df = pd.read_csv(CARROS_DATASET_PATH, sep=";", decimal=",", encoding="latin-1")
df_flex = df[df["combustivel"] == "F"]
df_sem_nulls = df_flex.dropna(subset=df_columns)

print(df_sem_nulls.head())

df_sem_nulls.to_csv(NOVO_CARROS_DATASET_PATH, sep=";", decimal=".", encoding="latin-1", index=False, columns=df_columns)
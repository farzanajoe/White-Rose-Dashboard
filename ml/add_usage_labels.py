import pandas as pd

df = pd.read_csv("clothing.csv")

def assign_usage_label(freq):
    if freq <= 3:
        return "Low"
    elif freq <= 8:
        return "Medium"
    else:
        return "High"

df["usage_label"] = df["Expected_Wear_Frequency_per_month"].apply(assign_usage_label)

df.to_csv("items_with_labels.csv", index=False)
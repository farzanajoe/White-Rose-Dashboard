import pandas as pd
from sklearn.preprocessing import OneHotEncoder
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
import joblib

# 1. Load your churn dataset
df = pd.read_csv("data/urbanfit_customer_churn_dataset.csv")

# 2. Features and target
features = [
    "age", "gender", "location", "tenure_months", "monthly_spend_gbp",
    "avg_weekly_sessions", "days_since_last_login", "app_engagement_type",
    "support_tickets_last_6m", "plan_type", "discount_received", "referral_source"
]
target = "churned"

X = df[features]
y = df[target]

# 3. Preprocessing
categorical = ["gender", "location", "app_engagement_type", "plan_type", "referral_source"]
numerical = ["age", "tenure_months", "monthly_spend_gbp", "avg_weekly_sessions",
             "days_since_last_login", "support_tickets_last_6m", "discount_received"]

preprocessor = ColumnTransformer(transformers=[
    ("cat", OneHotEncoder(handle_unknown="ignore"), categorical),
    ("num", "passthrough", numerical)
])

# 4. Pipeline
pipeline = Pipeline([
    ("preprocessing", preprocessor),
    ("classifier", RandomForestClassifier(n_estimators=200, random_state=42))
])

# 5. Train
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
pipeline.fit(X_train, y_train)

# 6. Accuracy
accuracy = pipeline.score(X_test, y_test)
print(f"Model Accuracy: {accuracy:.2f}")

# 7. Save — this creates churn_model.pkl
joblib.dump(pipeline, "churn_model.pkl")
print("churn_model.pkl saved successfully!")
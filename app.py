from flask import Flask, request, jsonify, render_template
import pandas as pd
import joblib
import numpy as np
import os

app = Flask(__name__)

# ── Auto-train model if it doesn't exist ────────────────────
if not os.path.exists("churn_model.pkl"):
    print("churn_model.pkl not found — training now...")

    from sklearn.preprocessing import OneHotEncoder
    from sklearn.model_selection import train_test_split
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.compose import ColumnTransformer
    from sklearn.pipeline import Pipeline

    df = pd.read_csv("data/urbanfit_customer_churn_dataset.csv")

    features = [
        "age", "gender", "location", "tenure_months", "monthly_spend_gbp",
        "avg_weekly_sessions", "days_since_last_login", "app_engagement_type",
        "support_tickets_last_6m", "plan_type", "discount_received", "referral_source"
    ]
    target = "churned"

    X = df[features]
    y = df[target]

    categorical = ["gender", "location", "app_engagement_type", "plan_type", "referral_source"]
    numerical   = ["age", "tenure_months", "monthly_spend_gbp", "avg_weekly_sessions",
                   "days_since_last_login", "support_tickets_last_6m", "discount_received"]

    preprocessor = ColumnTransformer(transformers=[
        ("cat", OneHotEncoder(handle_unknown="ignore"), categorical),
        ("num", "passthrough", numerical)
    ])

    pipeline = Pipeline([
        ("preprocessing", preprocessor),
        ("classifier", RandomForestClassifier(n_estimators=200, random_state=42))
    ])

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    pipeline.fit(X_train, y_train)

    accuracy = pipeline.score(X_test, y_test)
    print(f"Model Accuracy: {accuracy:.2f}")

    joblib.dump(pipeline, "churn_model.pkl")
    print("churn_model.pkl saved successfully!")

model = joblib.load("churn_model.pkl")

# ── Routes ───────────────────────────────────────────────────
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/result")
def result():
    return render_template("result.html")

@app.route("/predict", methods=["POST"])
def predict():
    data = request.json

    age                     = int(data["age"])
    gender                  = data["gender"]
    location                = data["location"].title()
    tenure_months           = int(data["tenure_months"])
    monthly_spend_gbp       = float(data["monthly_spend_gbp"])
    avg_weekly_sessions     = float(data["avg_weekly_sessions"])
    days_since_last_login   = int(data["days_since_last_login"])
    app_engagement_type     = data["app_engagement_type"]
    support_tickets_last_6m = int(data["support_tickets_last_6m"])
    plan_type               = data["plan_type"]
    discount_received       = int(data["discount_received"])
    referral_source         = data["referral_source"]

    new_customer = pd.DataFrame([{
        "age": age,
        "gender": gender,
        "location": location,
        "tenure_months": tenure_months,
        "monthly_spend_gbp": monthly_spend_gbp,
        "avg_weekly_sessions": avg_weekly_sessions,
        "days_since_last_login": days_since_last_login,
        "app_engagement_type": app_engagement_type,
        "support_tickets_last_6m": support_tickets_last_6m,
        "plan_type": plan_type,
        "discount_received": discount_received,
        "referral_source": referral_source
    }])

    prob = model.predict_proba(new_customer)[0, 1]

    if prob > 0.7:
        risk = "HIGH"
    elif prob > 0.4:
        risk = "MEDIUM"
    else:
        risk = "LOW"

    X_transformed = model.named_steps["preprocessing"].transform(new_customer)
    if hasattr(X_transformed, "toarray"):
        X_array = X_transformed.toarray()[0]
    else:
        X_array = np.array(X_transformed)[0]

    feature_names = model.named_steps["preprocessing"].get_feature_names_out()
    importances   = model.named_steps["classifier"].feature_importances_
    contributions = X_array * importances

    explain_df = pd.DataFrame({"Feature": feature_names, "Contribution": contributions})
    top3 = explain_df.reindex(
        explain_df["Contribution"].abs().sort_values(ascending=False).index
    ).head(3)
    drivers = [f.replace("num__", "").replace("cat__", "") for f in top3["Feature"].tolist()]

    short_term = []
    long_term  = []

    if age <= 25:
        short_term.append("Recommend short, high-energy workouts suitable for younger users.")
        long_term.append("Introduce gamified fitness challenges and social competitions.")
    if gender == "Female":
        short_term.append("Promote popular group workouts such as yoga or pilates.")
        long_term.append("Expand community-based group fitness programs.")
    if location in ["London", "Leeds", "Bristol", "Newcastle"]:
        short_term.append("Send city-based fitness campaigns or challenges.")
        long_term.append("Develop local fitness communities and events.")
    if tenure_months <= 3:
        short_term.append("Send onboarding reminders and workout guidance for new members.")
        long_term.append("Improve the onboarding journey to help users build habits early.")
    if monthly_spend_gbp > 70:
        short_term.append("Offer loyalty rewards for high-paying members.")
        long_term.append("Provide premium-exclusive features or classes.")
    if discount_received == 0:
        short_term.append("Provide a temporary retention discount or promotional offer.")
        long_term.append("Introduce a loyalty-based discount program.")
    if avg_weekly_sessions <= 2:
        short_term.append("Send reminders encouraging at least 3 workouts per week.")
        long_term.append("Introduce streak rewards or achievement badges.")
    if days_since_last_login >= 30:
        short_term.append("Send re-engagement notifications encouraging the user to return.")
        short_term.append("Email personalised workout suggestions.")
        long_term.append("Implement AI-based personalised workout recommendations.")
    if app_engagement_type == "On-Demand":
        short_term.append("Encourage participation in Live Classes.")
        long_term.append("Allow on-demand users to schedule upcoming sessions.")
    if support_tickets_last_6m >= 3:
        short_term.append("Prioritise faster customer support response.")
        long_term.append("Improve the customer support system to reduce response time.")
    if plan_type == "Basic":
        short_term.append("Promote additional features available in higher plans.")
        long_term.append("Introduce extra value benefits for Basic plan users.")
    if referral_source == "Paid Ad":
        short_term.append("Send targeted engagement emails for newly acquired users.")
        long_term.append("Improve marketing targeting to attract higher-retention customers.")

    short_term = list(set(short_term))[:5]
    long_term  = list(set(long_term))[:5]

    return jsonify({
        "probability": round(float(prob), 3),
        "risk": risk,
        "drivers": drivers,
        "short_term": short_term,
        "long_term": long_term
    })

if __name__ == "__main__":
    app.run(debug=True)
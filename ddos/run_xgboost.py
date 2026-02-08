
import xgboost as xgb
import numpy as np
import os

# --- Configuration ---
MODEL_FILE = "xgboost_model.bin"
# The model expects input with this many features (timesteps).
# This must match the 'lookback' parameter the model was trained with.
EXPECTED_FEATURES = 5

# --- Model Loading ---
print(f"Attempting to load XGBoost model from '{MODEL_FILE}'...")

# Check if the model file exists
if not os.path.exists(MODEL_FILE):
    print(f"\n--- ERROR ---")
    print(f"Model file not found: '{MODEL_FILE}'")
    print("Please make sure the model file is in the same directory as this script.")
    exit()

# Load the XGBoost model
model = xgb.XGBClassifier()
model.load_model(MODEL_FILE)

print("✅ XGBoost model loaded successfully.")

# --- Prediction ---
print("\n--- Running Prediction Example ---")

# Create a sample data point representing a sequence of packet counts.
# This simulates the input the model would receive.
# Shape: (1, EXPECTED_FEATURES)
sample_data_normal = np.array([10, 15, 12, 18, 14]).reshape(1, -1)
sample_data_attack = np.array([150, 200, 180, 220, 190]).reshape(1, -1)

print(f"\n1. Simulating NORMAL traffic with data: {sample_data_normal.flatten()}")

# Make a prediction
try:
    prediction_normal = model.predict(sample_data_normal)[0]
    prediction_proba_normal = model.predict_proba(sample_data_normal)[0]

    # --- Display Results ---
    if prediction_normal == 1:
        confidence = prediction_proba_normal[1] * 100
        print(f"   🚨 Result: ATTACK DETECTED (Confidence: {confidence:.2f}%)")
    else:
        confidence = prediction_proba_normal[0] * 100
        print(f"   ✅ Result: NORMAL traffic (Confidence: {confidence:.2f}%)")

except Exception as e:
    print(f"   ❌ Error during prediction: {e}")


print(f"\n2. Simulating ATTACK traffic with data: {sample_data_attack.flatten()}")

# Make a prediction
try:
    prediction_attack = model.predict(sample_data_attack)[0]
    prediction_proba_attack = model.predict_proba(sample_data_attack)[0]

    # --- Display Results ---
    if prediction_attack == 1:
        confidence = prediction_proba_attack[1] * 100
        print(f"   🚨 Result: ATTACK DETECTED (Confidence: {confidence:.2f}%)")
    else:
        confidence = prediction_proba_attack[0] * 100
        print(f"   ✅ Result: NORMAL traffic (Confidence: {confidence:.2f}%)")

except Exception as e:
    print(f"   ❌ Error during prediction: {e}")

print("\n--- Script Finished ---")


import torch
import pandas as pd
import numpy as np
import os
from statistics import mode
from sklearn.preprocessing import StandardScaler

# Import the TST model definition from the copied file
# This assumes tstplus.py is in the same directory
from tstplus import TSTPlus

# --- Configuration ---
MODEL_FILE = "tst_model.pth"
TRAIN_DATA_FILE = "train_ddos_data_0.1.csv"
TEST_DATA_FILE = "tcp_test_ddos_data_0.1.csv"

# This must match the sequence length the model was trained with.
SEQ_LENGTH = 400

# --- File Checks ---
print("--- Checking for necessary files ---")
required_files = [MODEL_FILE, TRAIN_DATA_FILE, TEST_DATA_FILE, "tstplus.py"]
all_files_found = True
for f in required_files:
    if not os.path.exists(f):
        print(f"❌ Error: File not found: '{f}'")
        all_files_found = False

if not all_files_found:
    print("\nPlease ensure all required files are in the same directory as this script.")
    exit()
else:
    print("✅ All necessary files found.")

# --- Model Loading ---
print(f"\n--- Loading TST Model ---")
print(f"Attempting to load model from '{MODEL_FILE}'...")

# Load the entire model (architecture and weights)
# Use map_location=torch.device('cpu') if you are not using a GPU
model = torch.load(MODEL_FILE, map_location=torch.device('cpu'))
model.eval()  # Set the model to evaluation mode

print("✅ TST model loaded successfully.")

# --- Data Preparation ---
print("\n--- Preparing Data for Prediction ---")

# 1. Load training data to fit the scaler
print(f"1. Loading training data '{TRAIN_DATA_FILE}' to fit the scaler...")
train_data = pd.read_csv(TRAIN_DATA_FILE)

# 2. Initialize and fit the StandardScaler
# The model was trained on scaled data, so we must apply the same transformation.
scaler = StandardScaler()
scaler.fit(train_data[['Mavlink_Count', 'Total_length']])
print("✅ Scaler fitted on training data.")

# 3. Load test data to get a sequence for prediction
print(f"\n2. Loading test data '{TEST_DATA_FILE}' to get a sample sequence...")
test_data = pd.read_csv(TEST_DATA_FILE)

# 4. Create a single sequence from the test data
# In a real application, this data would be coming from a live stream.
if len(test_data) >= SEQ_LENGTH:
    # Get the first possible sequence from the file
    x_sequence_raw = test_data['Mavlink_Count'].iloc[0:SEQ_LENGTH].values
    # Get the true label for this sequence for later comparison
    true_label = mode(test_data['Status'].iloc[0:SEQ_LENGTH+1].values)
    print(f"✅ Extracted a sample sequence of length {SEQ_LENGTH}.")
else:
    print(f"❌ Error: Test data has fewer than {SEQ_LENGTH} rows, cannot create a sequence.")
    exit()

# 5. Scale the sequence
# The scaler expects a 2D array, so we reshape our sequence, scale it, and then flatten it back.
# We create a dummy second column because the scaler was fitted on two features.
x_sequence_scaled = scaler.transform(np.hstack([x_sequence_raw.reshape(-1, 1), np.zeros((SEQ_LENGTH, 1))]))[:, 0]

# 6. Convert to a PyTorch Tensor
# The model expects the input tensor to have a specific shape: [batch_size, num_variables, sequence_length]
# For our case: [1, 1, 400]
x_tensor = torch.tensor(x_sequence_scaled, dtype=torch.float32).unsqueeze(0).unsqueeze(0)
print(f"✅ Sample sequence prepared and converted to tensor with shape: {x_tensor.shape}")

# --- Prediction ---
print("\n--- Running Prediction ---")

with torch.no_grad():  # Disable gradient calculation for inference
    # Get the raw output logits from the model
    output_logits = model(x_tensor)
    
    # Apply softmax to get probabilities
    probabilities = torch.nn.functional.softmax(output_logits, dim=1)
    
    # Get the predicted class index by finding the max probability
    predicted_index = torch.argmax(probabilities, dim=1).item()

# --- Display Results ---
print(f"   - Raw model output (logits): {output_logits.numpy().flatten()}")
print(f"   - Probabilities (Normal, Attack): {probabilities.numpy().flatten()}")
print(f"   - Predicted Class Index: {predicted_index}")

prediction_status = "ATTACK" if predicted_index == 1 else "NORMAL"

print(f"\n   ✅ Final Prediction: Traffic is {prediction_status}")
print(f"   - True Label for this sequence was: {'ATTACK' if true_label == 1 else 'NORMAL'}")

print("\n--- Script Finished ---")

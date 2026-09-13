# train_model.py
# This script trains a machine learning model to predict crop yield.
# Run this file ONCE (or whenever you want to retrain) using: python train_model.py
# It will save the trained model to the "models" folder so main.py can use it later.

import pandas as pd  # used to read and handle the CSV dataset
from sklearn.ensemble import RandomForestRegressor  # the ML model we are using
from sklearn.model_selection import train_test_split  # splits data into train/test sets
from sklearn.preprocessing import LabelEncoder  # converts text columns (like crop name) into numbers
import pickle  # used to save the trained model to a file

# Step 1: Load the dataset
# index_col=0 removes the extra unnamed index column that came with the CSV
data = pd.read_csv("../data/crop_data.csv", index_col=0)

# Step 2: Encode text columns into numbers
# Machine learning models only understand numbers, not words like "Wheat" or "India"
# LabelEncoder converts each unique text value into a number (e.g. Wheat -> 5)
area_encoder = LabelEncoder()
crop_encoder = LabelEncoder()

data["Area_encoded"] = area_encoder.fit_transform(data["Area"])
data["Item_encoded"] = crop_encoder.fit_transform(data["Item"])

# Step 3: Choose the input features (X) and the output we want to predict (y)
# NOTE: "Year" is intentionally NOT used as a feature.
# A Random Forest only learns patterns from years it has already seen -
# it cannot extrapolate into future years, it would just repeat old patterns.
# Since we want to predict UPCOMING yield (not historical), we drop Year
# and rely only on real environmental/agricultural conditions instead.
features = ["Area_encoded", "Item_encoded", "average_rain_fall_mm_per_year", "pesticides_tonnes", "avg_temp"]
X = data[features]
y = data["hg/ha_yield"]  # this is what we are trying to predict (the crop yield)

# Step 4: Split data into training set and testing set
# 80% of the data is used to train the model, 20% is kept aside to test how good it is
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Step 5: Create and train the Random Forest model
# n_estimators=60 means it builds 60 decision trees and averages their predictions
# max_depth=15 stops trees from growing too deep - keeps the saved model file small
# without losing much accuracy on a dataset this size
model = RandomForestRegressor(n_estimators=30, max_depth=12, random_state=42)
model.fit(X_train, y_train)  # this is where the actual "learning" happens

# Step 6: Check how good the model is on data it has never seen (X_test)
accuracy = model.score(X_test, y_test)  # returns R^2 score (closer to 1 = better)
print("Model R^2 accuracy on test data:", round(accuracy, 3))

# Step 7: Save the trained model and the encoders to files
# We need to save the encoders too, because later we must convert
# text input (like "Wheat") into the same numbers the model was trained on
with open("models/crop_model.pkl", "wb") as f:
    pickle.dump(model, f)

with open("models/area_encoder.pkl", "wb") as f:
    pickle.dump(area_encoder, f)

with open("models/crop_encoder.pkl", "wb") as f:
    pickle.dump(crop_encoder, f)

print("Model and encoders saved successfully in the 'models' folder.")

# =========================
# STEP 1: IMPORT LIBRARIES
# =========================
import pandas as pd
import numpy as np

np.random.seed(42)  # reproducibility

# =========================
# STEP 2: LOAD DATASET
# =========================
file_path = r"C:\Users\hp\Downloads\soil_moisture (2).csv"

try:
    df = pd.read_csv(file_path)
    print("Dataset loaded successfully!")
except Exception as e:
    raise Exception(f"Error loading file: {e}")

df.columns = df.columns.str.strip()

print("\nFirst 5 rows:")
print(df.head())

# =========================
# STEP 3: BASIC INFO
# =========================
print("\nDataset Info:")
print(df.info())

print("\nMissing Values:")
print(df.isnull().sum())

# =========================
# STEP 4: CLEANING FUNCTION
# =========================
def clean_data(df):
    df = df.drop_duplicates()

    if 'Status' in df.columns:
        df['Status'] = df['Status'].fillna(df['Status'].mode()[0])
        df['Status'] = df['Status'].astype(str).str.strip()

    return df

df = clean_data(df)

# =========================
# STEP 5: OUTLIER REMOVAL (IQR)
# =========================
def remove_outliers(df, columns):
    for col in columns:
        if col not in df.columns:
            print(f"Warning: {col} not found in dataset")
            continue

        Q1 = df[col].quantile(0.25)
        Q3 = df[col].quantile(0.75)
        IQR = Q3 - Q1

        lower = Q1 - 1.5 * IQR
        upper = Q3 + 1.5 * IQR

        df = df[(df[col] >= lower) & (df[col] <= upper)]

    return df

numeric_cols = ['Temperature', 'Humidity', 'Moisture']
df = remove_outliers(df, numeric_cols)

# =========================
# STEP 6: SAVE CLEANED DATA
# =========================
clean_path = "cleaned_soil_data.csv"
df.to_csv(clean_path, index=False)
print(f"\nCleaned dataset saved → {clean_path}")

# =========================
# STEP 7: DATA AUGMENTATION
# =========================
def augment_data(df, n_aug=5):
    augmented = []

    for _, row in df.iterrows():
        for _ in range(n_aug):

            temp = row['Temperature'] + np.random.normal(0, 1)
            humidity = row['Humidity'] + np.random.normal(0, 2)
            moisture = row['Moisture'] + np.random.normal(0, 50)

            augmented.append({
                'Temperature': round(np.clip(temp, 10, 50), 2),
                'Humidity': round(np.clip(humidity, 0, 100), 2),
                'Moisture': int(np.clip(moisture, 0, 4095)),
                'Status': row['Status']
            })

    return pd.DataFrame(augmented)

aug_df = augment_data(df, n_aug=5)

# =========================
# STEP 8: COMBINE DATA
# =========================
final_df = pd.concat([df, aug_df], ignore_index=True)

# shuffle dataset (important for ML training)
final_df = final_df.sample(frac=1, random_state=42).reset_index(drop=True)

# =========================
# STEP 9: SAVE FINAL DATA
# =========================
final_path = "augmented_soil_data.csv"
final_df.to_csv(final_path, index=False)

print("\n===== DATA SUMMARY =====")
print("Original Data :", len(df))
print("Augmented Data:", len(aug_df))
print("Final Data    :", len(final_df))
print(f"Saved → {final_path}")
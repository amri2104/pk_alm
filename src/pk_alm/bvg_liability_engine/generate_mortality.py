import csv
import math

with open("src/pk_alm/bvg_liability_engine/mortality_table.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["age", "male_qx", "female_qx"])
    for age in range(121):
        if age < 120:
            # Gompertz-Makeham roughly
            # a + b * exp(c * age)
            # male_qx a bit higher than female
            male_qx = 0.0005 + 0.00002 * math.exp(0.09 * age)
            female_qx = 0.0004 + 0.000015 * math.exp(0.085 * age)
            
            # cap at 1.0
            male_qx = min(1.0, male_qx)
            female_qx = min(1.0, female_qx)
        else:
            male_qx = 1.0
            female_qx = 1.0
            
        writer.writerow([age, round(male_qx, 6), round(female_qx, 6)])

print("Mortality table generated.")

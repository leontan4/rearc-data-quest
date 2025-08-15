import io, json, boto3
import pandas as pd
from datetime import date
from botocore.exceptions import ClientError

S3_BUCKET  = "rearc-raw-bucket-dev"
BLS_KEY    = "bls/pr/"
CENSUS_KEY = f"census/"

s3 = boto3.client('s3')

def main():
    bls_data = read_bls(S3_BUCKET, BLS_KEY, "pr.data.0.Current")
    census_data = read_census(S3_BUCKET, CENSUS_KEY, date.today().isoformat(),"census.json")
    generate_report(bls_data, census_data)
    # print(bls_data)
    # print(generate_report())

def read_bls(s3_bucket: str, s3_key: str, file_name: str) -> pd.DataFrame:
    """Load and return BLS data"""
    s3_key = f"{s3_key}{file_name}"
    print(s3_key)

    try:
        response = s3.get_object(
            Bucket=s3_bucket,
            Key=s3_key
        )

        bls_df = pd.read_csv(
            io.BytesIO(response["Body"].read()),
            compression="gzip",
            sep="\t"
        )

        bls_df.columns = (
            bls_df.columns
            .str.strip()
            .str.lower()
            .str.replace(" ", "_")
        )
        return bls_df

    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            print("BLS data does not exists")

    return pd.DataFrame()

def read_census(s3_bucket: str, s3_key: str, file_date: str, file_name: str) -> pd.DataFrame:
    """Load and return census data frame"""

    s3_key = f"{s3_key}{file_date}/{file_name}"

    try:
        response = s3.get_object(
            Bucket=s3_bucket,
            Key=s3_key
        )

        payload = json.loads(response["Body"].read())
        census_data = payload["data"]
        census_df = pd.DataFrame(census_data)

        census_df.columns = (
            census_df.columns
            .str.strip()
            .str.lower()
            .str.replace(" ", "_")
        )
        return census_df

    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            print("Census data does not exists")

    return pd.DataFrame()

def generate_report(bls_data: pd.DataFrame, census_data: pd.DataFrame) -> pd.DataFrame:
    """Generating report for census and bls"""

    # Generating mean and std for census data
    census_2013_2018 = census_data[
        (census_data["year"] >= 2013) &
        (census_data["year"] <= 2018)
        ].copy()

    census_mean = round(float(census_2013_2018["population"].mean()), 2)
    census_std = round(float(census_2013_2018["population"].std()), 2)

    census_stats = pd.DataFrame({
        "metric": ["mean_population_2013_2018", "std_population_2013_2018"],
        "value": [census_mean, census_std]
    })

    print(census_stats)

    # Generating max total value of series for bls
    bls_grouped = (bls_data
                       .groupby(["series_id", "year"], as_index=False)["value"]
                       .sum()
                       .rename(columns={"value": "total_value"})
                   )

    bls_best_years = (bls_grouped
                          .loc[bls_grouped.groupby("series_id")["total_value"]
                          .idxmax()]
                          .reset_index(drop=True)
                          .sort_values(["series_id", "year", "total_value"], ascending=[True, False, False])
                      )

    bls_6032_q1 = bls_data.loc[
                    (bls_data["series_id"].str.strip() == "PRS30006032") &
                    (bls_data["year"] == 2018) &
                    (bls_data["period"].str.strip() == "Q01"),
                    ["series_id", "year", "period", "value"]
                ]

    bls_census_merged_df = pd.merge(
        census_data,
        bls_6032_q1,
        left_on="year",
        right_on="year",
        how="inner"
    )
    return bls_6032_q1



if __name__ == "__main__":
    main()

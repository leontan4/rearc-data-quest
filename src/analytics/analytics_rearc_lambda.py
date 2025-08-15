import io, json, boto3, logging, os
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from datetime import datetime, timezone
from typing import Dict, Any
from botocore.config import Config
from botocore.exceptions import ClientError, ReadTimeoutError, ConnectTimeoutError

# CONFIG
UTC_DATE      = datetime.now(timezone.utc).date().isoformat()
S3_BUCKET     = os.environ.get("s3_bucket")
S3_BLS        = os.environ.get("s3_bls_key")
S3_CENSUS_KEY = os.environ.get("s3_census_key")
S3_CENSUS     = f"{S3_CENSUS_KEY}{UTC_DATE}/census.json"
S3_MERGED     = f"analytics/{UTC_DATE}/bls_census_stats.parquet"

s3_config = Config(connect_timeout=5, read_timeout=15, retries={"max_attempts": 3})
s3 = boto3.client("s3", config=s3_config)

# Initiate logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def handler(event, context) -> Dict[str, Any]:

    try:
        bls_data = read_bls("pr.data.0.Current")
        census_data = read_census()
        res = generate_report(bls_data, census_data)
        upload_parquet_to_s3(res)
        return {
            "statusCode": 200,
            "body": json.dumps({
                "message": "Report generated successfully",
                "numRows": f"Number of rows of data: {len(res)}"
            })
        }

    except (ReadTimeoutError, ConnectTimeoutError) as timeoutErr:
        logger.error(f"S3 timeout: {timeoutErr}")
        return {
            "statusCode": 504,
            "body": json.dumps({
                "message": "S3 timeout error",
                "error": str(timeoutErr)
            })
        }

    except Exception as err:
        logger.error(f"Handler failed: {err}")

        return {
            "statusCode": 500,
            "body": json.dumps({
                "message": "Handler failed",
                "error": str(err)
            })
        }

def read_bls(file_name: str) -> pd.DataFrame:
    """Load and return BLS data"""
    s3_key = f"{S3_BLS}/{file_name}"

    try:
        response = s3.get_object(
            Bucket=S3_BUCKET,
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
        logger.error(f"BLS path: {s3_key}")
        if e.response["Error"]["Code"] == "NoSuchKey":
            logger.error("BLS data does not exists")

    return pd.DataFrame()

def read_census() -> pd.DataFrame:
    """Load and return census data frame"""
    try:
        response = s3.get_object(
            Bucket=S3_BUCKET,
            Key=S3_CENSUS
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
        logger.error(f"Census path: {S3_CENSUS}")
        if e.response["Error"]["Code"] == "NoSuchKey":
            logger.error("Census data does not exists")

    return pd.DataFrame()

def upload_parquet_to_s3(df: pd.DataFrame) -> None:
    """
    Serialize a DataFrame to Parquet and upload to S3.
    """
    res_df = pa.Table.from_pandas(df)

    # Write Parquet to buffer
    buffer = io.BytesIO()
    pq.write_table(res_df, buffer)
    buffer.seek(0)

    # Upload to S3
    s3.put_object(
        Bucket=S3_BUCKET,
        Key=S3_MERGED,
        Body=buffer.getvalue(),
        ContentType="application/x-parquet",
        ServerSideEncryption="AES256"  # optional, keep if you want SSE-S3
    )

    logger.info(f"Merged DataFrame uploaded to s3://{S3_BUCKET}/{S3_MERGED}")


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

    return bls_census_merged_df
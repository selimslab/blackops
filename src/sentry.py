import sentry_sdk

sentry_sdk.init(
    "https://d979f35244e74fe4b0cfeea01b362d78@o1115374.ingest.sentry.io/6147287",
    # Set traces_sample_rate to 1.0 to capture 100%
    # of transactions for performance monitoring.
    # We recommend adjusting this value in production.
    traces_sample_rate=1.0,
)

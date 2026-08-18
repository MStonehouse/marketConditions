#!/usr/bin/env python3

import os
import json
import math
import time
import statistics

from pathlib import Path
from datetime import date, datetime, timedelta, timezone
from urllib.request import Request, urlopen
from urllib.parse import urlencode


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "dashboard.json"

FRED_API_URL = (
    "https://api.stlouisfed.org/fred/series/observations"
)

FRED_API_KEY = os.environ.get("FRED_API_KEY")


# =========================================================
# ECONOMIC CONDITIONS MODEL
# =========================================================
#
# NO market-derived inputs are used in this model.
#

ECON = {
    "M2SL": (
        "Money & Liquidity",
        "M2 money stock",
        15,
        "growth",
        24,
    ),

    "TOTBKCR": (
        "Bank Credit",
        "Total bank credit",
        10,
        "growth",
        9,
    ),

    "BUSLOANS": (
        "Business Lending",
        "Commercial & industrial loans",
        5,
        "growth",
        9,
    ),

    "CPATAX": (
        "Corporate Health",
        "Corporate profits after tax",
        15,
        "growth",
        65,
    ),

    "INDPRO": (
        "Real Economic Activity",
        "Industrial production",
        15,
        "growth",
        18,
    ),

    "PAYEMS": (
        "Employment",
        "Total nonfarm payrolls",
        10,
        "growth",
        8,
    ),

    "RSAFS": (
        "Consumer Activity",
        "Retail & food services sales",
        5,
        "growth",
        17,
    ),

    "DSPIC96": (
        "Consumer Income",
        "Real disposable personal income",
        5,
        "growth",
        32,
    ),

    "CPIAUCSL": (
        "Inflation Environment",
        "CPI inflation",
        10,
        "inflation",
        15,
    ),

    "DGORDER": (
        "Business Investment",
        "Durable goods new orders",
        5,
        "growth",
        28,
    ),

    "FEDFUNDS": (
        "Monetary Policy",
        "Effective federal funds rate",
        5,
        "policy",
        2,
    ),
}


# =========================================================
# INVESTOR SENTIMENT MODEL
# =========================================================
#
# This model is intentionally completely separate from ECON.
#

SENT = {
    "VIXCLS": (
        "Implied Volatility",
        "CBOE VIX",
        30,
        "inverse_level",
    ),

    "BAMLH0A0HYM2": (
        "Risk Appetite",
        "High-yield option-adjusted spread",
        25,
        "inverse_level",
    ),

    "STLFSI4": (
        "Financial Stress",
        "St. Louis Fed Financial Stress Index",
        20,
        "inverse_level",
    ),

    "SP500": (
        "Market Momentum",
        "S&P 500 short-term momentum",
        15,
        "momentum",
    ),

    "NASDAQCOM": (
        "Growth-Risk Appetite",
        "NASDAQ short-term momentum",
        10,
        "momentum",
    ),
}


# =========================================================
# FRED API
# =========================================================


def fetch(sid):
    if not FRED_API_KEY:
        raise RuntimeError(
            "FRED_API_KEY environment variable is missing."
        )

    params = {
        "series_id": sid,
        "api_key": FRED_API_KEY,
        "file_type": "json",
        "observation_start": "2005-01-01",
    }

    url = (
        FRED_API_URL
        + "?"
        + urlencode(params)
    )

    last_error = None

    for attempt in range(1, 4):

        try:
            print(
                f"Downloading {sid} "
                f"(attempt {attempt}/3)"
            )

            request = Request(
                url,
                headers={
                    "User-Agent":
                    "MarketConditionsDashboard/1.0"
                },
            )

            with urlopen(
                request,
                timeout=60,
            ) as response:

                raw = response.read().decode(
                    "utf-8"
                )

            payload = json.loads(raw)

            if "error_message" in payload:
                raise RuntimeError(
                    payload["error_message"]
                )

            observations = payload.get(
                "observations",
                [],
            )

            rows = []

            for observation in observations:

                value = observation.get(
                    "value"
                )

                obs_date = observation.get(
                    "date"
                )

                if (
                    not value
                    or value == "."
                    or not obs_date
                ):
                    continue

                try:
                    rows.append(
                        (
                            date.fromisoformat(
                                obs_date
                            ),
                            float(value),
                        )
                    )

                except Exception:
                    continue

            rows.sort()

            if not rows:
                raise RuntimeError(
                    f"No usable data returned "
                    f"for {sid}"
                )

            print(
                f"{sid}: "
                f"{len(rows)} observations"
            )

            return rows

        except Exception as error:

            last_error = error

            print(
                f"Attempt {attempt} failed "
                f"for {sid}: {error}"
            )

            if attempt < 3:
                time.sleep(5)

    raise RuntimeError(
        f"Failed to download "
        f"{sid} after 3 attempts"
    ) from last_error


# =========================================================
# GENERAL HELPERS
# =========================================================


def last_before(
    rows,
    target_date,
):

    lo = 0
    hi = len(rows)

    while lo < hi:

        mid = (
            lo + hi
        ) // 2

        if (
            rows[mid][0]
            <= target_date
        ):
            lo = mid + 1

        else:
            hi = mid

    if lo == 0:
        return None

    return rows[lo - 1]


def clamp(
    value,
    minimum,
    maximum,
):

    return max(
        minimum,
        min(
            maximum,
            value,
        ),
    )


def logistic(z):

    z = clamp(
        z,
        -4,
        4,
    )

    return (
        100
        /
        (
            1
            + math.exp(
                -1.12 * z
            )
        )
    )


def robust(values):

    values = [
        value
        for value in values
        if (
            value is not None
            and math.isfinite(value)
        )
    ]

    if len(values) < 8:
        return 0, 1

    median = statistics.median(
        values
    )

    mad = statistics.median(
        abs(
            value - median
        )
        for value in values
    )

    scale = 1.4826 * mad

    if scale < 1e-6:

        scale = (
            statistics.pstdev(
                values
            )
            or 1
        )

    return (
        median,
        max(
            scale,
            1e-6,
        ),
    )


def yoy(
    rows,
    item,
):

    if not item:
        return None

    previous = last_before(
        rows,
        item[0]
        - timedelta(
            days=365
        ),
    )

    if not previous:
        return None

    if previous[1] == 0:
        return None

    return (
        (
            item[1]
            / previous[1]
        )
        - 1
    ) * 100


# =========================================================
# ECONOMIC COMPONENT SCORING
# =========================================================


def econ_component(
    sid,
    asof,
    rows,
):

    (
        name,
        detail,
        weight,
        kind,
        lag_days,
    ) = ECON[sid]

    current = last_before(
        rows,
        asof
        - timedelta(
            days=lag_days
        ),
    )

    previous = last_before(
        rows,
        asof
        - timedelta(
            days=lag_days + 92
        ),
    )

    if not current:
        return None


    # -----------------------------------------------------
    # GROWTH VARIABLES
    # -----------------------------------------------------

    if kind == "growth":

        current_growth = yoy(
            rows,
            current,
        )

        previous_growth = yoy(
            rows,
            previous,
        )

        history_start = (
            asof
            - timedelta(
                days=3650
            )
        )

        history = []

        for item in rows:

            if (
                history_start
                <= item[0]
                <= current[0]
            ):

                growth = yoy(
                    rows,
                    item,
                )

                if growth is not None:
                    history.append(
                        growth
                    )

        median, scale = robust(
            history
        )

        if current_growth is None:
            current_growth = median

        level_score = logistic(
            (
                current_growth
                - median
            )
            /
            max(
                scale,
                0.25,
            )
        )

        if previous_growth is None:

            acceleration_score = 50

        else:

            acceleration_score = logistic(
                (
                    current_growth
                    - previous_growth
                )
                /
                max(
                    scale * 0.5,
                    0.35,
                )
            )

        score = (
            0.68
            * level_score
            +
            0.32
            * acceleration_score
        )

        epsilon = max(
            scale * 0.12,
            0.15,
        )

        if previous_growth is None:

            direction = "→"

        elif (
            current_growth
            > previous_growth
            + epsilon
        ):

            direction = "↑"

        elif (
            current_growth
            < previous_growth
            - epsilon
        ):

            direction = "↓"

        else:

            direction = "→"


    # -----------------------------------------------------
    # INFLATION
    # -----------------------------------------------------

    elif kind == "inflation":

        current_growth = yoy(
            rows,
            current,
        )

        previous_growth = yoy(
            rows,
            previous,
        )

        if current_growth is None:
            return None

        current_distance = abs(
            current_growth - 2
        )

        level_score = (
            100
            - clamp(
                (
                    current_distance
                    / 5
                )
                * 100,
                0,
                100,
            )
        )

        if previous_growth is None:

            direction_score = 50
            direction = "→"

        else:

            previous_distance = abs(
                previous_growth - 2
            )

            improvement = (
                previous_distance
                - current_distance
            )

            direction_score = logistic(
                improvement
                / 0.45
            )

            if (
                current_distance
                < previous_distance
                - 0.08
            ):

                direction = "↑"

            elif (
                current_distance
                > previous_distance
                + 0.08
            ):

                direction = "↓"

            else:

                direction = "→"

        score = (
            0.72
            * level_score
            +
            0.28
            * direction_score
        )


    # -----------------------------------------------------
    # POLICY RATE
    # -----------------------------------------------------

    elif kind == "policy":

        rate = current[1]

        previous_rate = (
            previous[1]
            if previous
            else rate
        )

        level_score = logistic(
            (
                2.5 - rate
            )
            / 1.8
        )

        direction_score = logistic(
            (
                previous_rate
                - rate
            )
            / 0.65
        )

        score = (
            0.70
            * level_score
            +
            0.30
            * direction_score
        )

        if (
            rate
            < previous_rate
            - 0.10
        ):

            direction = "↑"

        elif (
            rate
            > previous_rate
            + 0.10
        ):

            direction = "↓"

        else:

            direction = "→"

    else:

        return None


    return {
        "name": name,
        "detail": detail,
        "weight": weight,
        "score": round(
            clamp(
                score,
                0,
                100,
            ),
            1,
        ),
        "direction": direction,
    }


def econ_score(
    asof,
    series,
):

    parts = []

    numerator = 0
    denominator = 0

    for sid in ECON:

        component = econ_component(
            sid,
            asof,
            series[sid],
        )

        if component:

            parts.append(
                component
            )

            numerator += (
                component["score"]
                *
                component["weight"]
            )

            denominator += (
                component["weight"]
            )

    if denominator == 0:

        return (
            None,
            [],
        )

    return (
        numerator
        / denominator,
        parts,
    )


# =========================================================
# SENTIMENT SCORING
# =========================================================


def window_values(
    rows,
    asof,
    days=3650,
):

    start = (
        asof
        - timedelta(
            days=days
        )
    )

    return [
        value
        for (
            observation_date,
            value,
        )
        in rows
        if (
            start
            <= observation_date
            <= asof
        )
    ]


def sent_component(
    sid,
    asof,
    rows,
):

    (
        name,
        detail,
        weight,
        kind,
    ) = SENT[sid]

    current = last_before(
        rows,
        asof,
    )

    if not current:
        return None


    # -----------------------------------------------------
    # MOMENTUM
    # -----------------------------------------------------

    if kind == "momentum":

        one_month_ago = last_before(
            rows,
            asof
            - timedelta(
                days=30
            ),
        )

        one_week_ago = last_before(
            rows,
            asof
            - timedelta(
                days=7
            ),
        )

        if not one_month_ago:
            return None

        return_1m = (
            (
                current[1]
                / one_month_ago[1]
            )
            - 1
        ) * 100

        if one_week_ago:

            return_1w = (
                (
                    current[1]
                    / one_week_ago[1]
                )
                - 1
            ) * 100

        else:

            return_1w = return_1m

        combined = (
            0.7
            * return_1m
            +
            0.3
            * return_1w
        )

        score = logistic(
            combined / 4
        )

        if return_1w > 1:

            direction = "↑"

        elif return_1w < -1:

            direction = "↓"

        else:

            direction = "→"


    # -----------------------------------------------------
    # STRESS / FEAR INDICATORS
    # -----------------------------------------------------

    else:

        values = window_values(
            rows,
            asof,
        )

        median, scale = robust(
            values
        )

        z = (
            current[1]
            - median
        ) / max(
            scale,
            0.01,
        )

        score = (
            100
            - logistic(z)
        )

        one_month_ago = last_before(
            rows,
            asof
            - timedelta(
                days=30
            ),
        )

        if not one_month_ago:

            direction = "→"

        else:

            delta = (
                current[1]
                - one_month_ago[1]
            )

            epsilon = max(
                scale * 0.08,
                0.02,
            )

            if delta < -epsilon:

                direction = "↑"

            elif delta > epsilon:

                direction = "↓"

            else:

                direction = "→"


    return {
        "name": name,
        "detail": detail,
        "weight": weight,
        "score": round(
            clamp(
                score,
                0,
                100,
            ),
            1,
        ),
        "direction": direction,
    }


def sent_score(
    asof,
    series,
):

    parts = []

    numerator = 0
    denominator = 0

    for sid in SENT:

        component = sent_component(
            sid,
            asof,
            series[sid],
        )

        if component:

            parts.append(
                component
            )

            numerator += (
                component["score"]
                *
                component["weight"]
            )

            denominator += (
                component["weight"]
            )

    if denominator == 0:

        return (
            None,
            [],
        )

    return (
        numerator
        / denominator,
        parts,
    )


# =========================================================
# CLASSIFICATION
# =========================================================


def econ_class(score):

    if score >= 80:
        return "Exceptional"

    if score >= 65:
        return "Favorable"

    if score >= 55:
        return "Moderately Favorable"

    if score >= 45:
        return "Neutral"

    if score >= 35:
        return "Moderately Unfavorable"

    if score >= 20:
        return "Unfavorable"

    return "Severe"


def direction(
    current,
    previous,
    epsilon=1.5,
):

    if current > previous + epsilon:
        return "↑"

    if current < previous - epsilon:
        return "↓"

    return "→"


# =========================================================
# MAIN
# =========================================================


def main():

    print("")
    print(
        "========================================"
    )
    print(
        "Market Conditions Dashboard"
    )
    print(
        "========================================"
    )

    if not FRED_API_KEY:

        raise RuntimeError(
            "FRED_API_KEY was not passed "
            "to the workflow."
        )

    ids = sorted(
        set(ECON)
        | set(SENT)
    )

    series = {}


    # -----------------------------------------------------
    # DOWNLOAD
    # -----------------------------------------------------

    print("")
    print(
        "Downloading FRED series..."
    )

    for sid in ids:

        series[sid] = fetch(
            sid
        )


    today = date.today()

    start = (
        today
        - timedelta(
            days=int(
                365.25 * 10
            )
        )
    )


    # -----------------------------------------------------
    # BUILD 10-YEAR HISTORY
    # -----------------------------------------------------

    print("")
    print(
        "Building 10-year history..."
    )

    history = []

    current_date = start

    while current_date <= today:

        if current_date.weekday() < 5:

            economic_score, _ = (
                econ_score(
                    current_date,
                    series,
                )
            )

            sentiment_score, _ = (
                sent_score(
                    current_date,
                    series,
                )
            )

            sp500 = last_before(
                series["SP500"],
                current_date,
            )

            if (
                economic_score
                is not None
                and sentiment_score
                is not None
            ):

                history.append(
                    {
                        "date":
                            current_date.isoformat(),

                        "economic":
                            round(
                                economic_score,
                                1,
                            ),

                        "sentiment":
                            round(
                                sentiment_score,
                                1,
                            ),

                        "sp500":
                            (
                                None
                                if not sp500
                                else round(
                                    sp500[1],
                                    2,
                                )
                            ),
                    }
                )

        current_date += timedelta(
            days=1
        )


    print(
        f"Historical rows: "
        f"{len(history)}"
    )


    # -----------------------------------------------------
    # CURRENT ECONOMIC SCORE
    # -----------------------------------------------------

    economic_score, economic_parts = (
        econ_score(
            today,
            series,
        )
    )

    economic_3m, _ = (
        econ_score(
            today
            - timedelta(
                days=92
            ),
            series,
        )
    )


    # -----------------------------------------------------
    # CURRENT SENTIMENT SCORE
    # -----------------------------------------------------

    sentiment_score, sentiment_parts = (
        sent_score(
            today,
            series,
        )
    )

    sentiment_1m, _ = (
        sent_score(
            today
            - timedelta(
                days=30
            ),
            series,
        )
    )


    # -----------------------------------------------------
    # CURRENT S&P 500
    # -----------------------------------------------------

    sp500_current = last_before(
        series["SP500"],
        today,
    )

    sp500_1m = last_before(
        series["SP500"],
        today
        - timedelta(
            days=30
        ),
    )


    if (
        sp500_current
        and sp500_1m
    ):

        sp500_change = (
            (
                sp500_current[1]
                / sp500_1m[1]
            )
            - 1
        ) * 100

    else:

        sp500_change = None


    # -----------------------------------------------------
    # OUTPUT JSON
    # -----------------------------------------------------

    payload = {

        "generated_at":
            datetime.now(
                timezone.utc
            ).strftime(
                "%Y-%m-%d %H:%M UTC"
            ),

        "current": {

            "economic": {

                "score":
                    round(
                        economic_score,
                        1,
                    ),

                "classification":
                    econ_class(
                        economic_score
                    ),

                "direction":
                    direction(
                        economic_score,
                        economic_3m,
                    ),

                "change_3m":
                    round(
                        economic_score
                        - economic_3m,
                        1,
                    ),

                "components":
                    economic_parts,
            },


            "sentiment": {

                "score":
                    round(
                        sentiment_score,
                        1,
                    ),

                "direction":
                    direction(
                        sentiment_score,
                        sentiment_1m,
                    ),

                "change_1m":
                    round(
                        sentiment_score
                        - sentiment_1m,
                        1,
                    ),

                "components":
                    sentiment_parts,
            },


            "sp500": {

                "value":
                    (
                        None
                        if not sp500_current
                        else round(
                            sp500_current[1],
                            2,
                        )
                    ),

                "change_1m":
                    (
                        None
                        if sp500_change
                        is None
                        else round(
                            sp500_change,
                            2,
                        )
                    ),
            },
        },


        "history":
            history,


        "meta": {

            "history_years":
                10,

            "economic_model_uses_market_data":
                False,

            "sentiment_model_is_separate":
                True,

            "sp500_is_display_only":
                True,

            "fred_source":
                "Official FRED API",
        },
    }


    OUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUT.write_text(
        json.dumps(
            payload,
            separators=(
                ",",
                ":",
            ),
        )
    )


    print("")
    print(
        "========================================"
    )
    print(
        "SUCCESS"
    )
    print(
        "========================================"
    )

    print(
        f"Economic score: "
        f"{economic_score:.1f}"
    )

    print(
        f"Sentiment score: "
        f"{sentiment_score:.1f}"
    )

    print(
        f"Saved to: {OUT}"
    )


if __name__ == "__main__":
    main()

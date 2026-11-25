"""Estimate the value of AI agent adoption for an engineering team."""

import argparse
import decimal
import html
import math
import sys
from dataclasses import dataclass
from typing import List, Sequence, Tuple


@dataclass
class YearResult:
    year: int
    adoption_percent: float
    value: float
    cost: float
    net: float
    cumulative_net: float


@dataclass
class RoiResult:
    hourly_cost: float
    hours_saved_per_year: float
    annual_value: float
    annual_cost: float
    net_value: float
    roi_percent: float
    payback_months: float
    engineers: int
    loaded_annual_cost: float
    hours_saved_per_week: float
    working_weeks: int
    hours_per_week: float
    ramp: Tuple[float, float, float]
    years: List[YearResult]
    three_year_value: float
    three_year_cost: float
    three_year_net: float
    three_year_roi_percent: float
    first_year_payback_months: float


DEFAULT_RAMP = (50.0, 80.0, 100.0)
RAMP_ERROR = "--ramp must be three percentages from 0 to 100, for example 50,80,100"
TOO_LARGE = "inputs are too large to produce a meaningful estimate"


def _too_large(value) -> bool:
    # Python ints can exceed the float range; math.isfinite would raise on them.
    try:
        float(value)
    except OverflowError:
        return True
    return False


def _is_finite(value) -> bool:
    return math.isfinite(value)


def _validate_ramp(ramp: Sequence[float]) -> Tuple[float, float, float]:
    try:
        values = tuple(ramp)
    except TypeError:
        raise ValueError(RAMP_ERROR) from None
    if len(values) != 3:
        raise ValueError(RAMP_ERROR)
    for v in values:
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise ValueError(RAMP_ERROR)
        if _too_large(v) or not _is_finite(v) or not 0 <= v <= 100:
            raise ValueError(RAMP_ERROR)
    # Adding 0.0 turns -0.0 into 0.0 so it never displays as "-0%".
    return tuple(float(v) + 0.0 for v in values)


def parse_ramp(text: str) -> Tuple[float, float, float]:
    try:
        values = [float(part) for part in text.split(",")]
    except ValueError:
        raise ValueError(RAMP_ERROR) from None
    return _validate_ramp(values)


def _payback_months(annual_tool_cost: float, annual_value: float) -> float:
    # The licence is paid at the start of each year, so it only pays back within
    # a year if that year's value exceeds the cost.
    if annual_value > annual_tool_cost:
        return annual_tool_cost / (annual_value / 12)
    return float("inf")


def calculate_roi(
    engineers: int,
    loaded_annual_cost: float,
    hours_saved_per_week: float,
    annual_tool_cost: float,
    working_weeks: int = 46,
    hours_per_week: float = 40,
    ramp: Sequence[float] = DEFAULT_RAMP,
) -> RoiResult:
    inputs = (engineers, loaded_annual_cost, hours_saved_per_week, annual_tool_cost,
              working_weeks, hours_per_week)
    if any(_too_large(v) for v in inputs):
        raise ValueError(TOO_LARGE)
    if not _is_finite(engineers) or engineers <= 0:
        raise ValueError("--engineers must be greater than 0")
    if not _is_finite(loaded_annual_cost) or loaded_annual_cost <= 0:
        raise ValueError("--loaded-cost must be a number greater than 0")
    if not _is_finite(annual_tool_cost) or annual_tool_cost <= 0:
        raise ValueError("--tool-cost must be a number greater than 0")
    if not _is_finite(working_weeks) or not 1 <= working_weeks <= 52:
        raise ValueError("--weeks must be between 1 and 52")
    if not _is_finite(hours_per_week) or hours_per_week <= 0:
        raise ValueError("hours per week must be a number greater than 0")
    if not _is_finite(hours_saved_per_week) or not (
        0 <= hours_saved_per_week <= hours_per_week
    ):
        raise ValueError(
            f"--hours-saved must be between 0 and {hours_per_week:g} "
            "(the hours in a working week)"
        )
    ramp = _validate_ramp(ramp)

    hourly_cost = loaded_annual_cost / (working_weeks * hours_per_week)
    hours_saved_per_year = engineers * hours_saved_per_week * working_weeks
    annual_value = hours_saved_per_year * hourly_cost
    net_value = annual_value - annual_tool_cost
    roi_percent = net_value / annual_tool_cost * 100
    payback_months = _payback_months(annual_tool_cost, annual_value)

    years = []
    cumulative_net = 0.0
    for year, adoption in enumerate(ramp, start=1):
        value = annual_value * adoption / 100
        net = value - annual_tool_cost
        cumulative_net += net
        years.append(YearResult(year, adoption, value, annual_tool_cost, net, cumulative_net))
    three_year_value = sum(y.value for y in years)
    three_year_cost = annual_tool_cost * len(years)
    three_year_net = three_year_value - three_year_cost
    three_year_roi_percent = three_year_net / three_year_cost * 100
    first_year_payback_months = _payback_months(annual_tool_cost, years[0].value)

    # Finite inputs can still overflow, e.g. a loaded cost of 1e308.
    if not all(_is_finite(v) for v in (hourly_cost, annual_value, net_value, roi_percent,
                                       three_year_value, three_year_cost,
                                       three_year_net, three_year_roi_percent)):
        raise ValueError(TOO_LARGE)
    return RoiResult(
        hourly_cost=hourly_cost,
        hours_saved_per_year=hours_saved_per_year,
        annual_value=annual_value,
        annual_cost=annual_tool_cost,
        net_value=net_value,
        roi_percent=roi_percent,
        payback_months=payback_months,
        engineers=engineers,
        loaded_annual_cost=loaded_annual_cost,
        hours_saved_per_week=hours_saved_per_week,
        working_weeks=working_weeks,
        hours_per_week=hours_per_week,
        ramp=ramp,
        years=years,
        three_year_value=three_year_value,
        three_year_cost=three_year_cost,
        three_year_net=three_year_net,
        three_year_roi_percent=three_year_roi_percent,
        first_year_payback_months=first_year_payback_months,
    )


CURRENCY_SYMBOLS = {"USD": "$", "GBP": "£", "EUR": "€"}


# Official Factory logos, from factory.ai (retrieved 2026-11-25). Both use
# fill="currentColor", so they take on the page's text color.
FACTORY_WORDMARK = '<svg width="127" height="19" viewBox="0 0 127 19" fill="none" xmlns="http://www.w3.org/2000/svg"><title>Factory</title><path d="M28.3945 15.8524V2.62109H38.3002V4.98361H31.0123V8.08378H37.5247V10.3707H31.0123V15.8524H28.3945Z" fill="currentColor"></path><path d="M40.0078 15.8524L44.0729 4.47837C44.2668 3.93574 44.6291 3.46542 45.1098 3.13264C45.5902 2.79987 46.1646 2.62105 46.754 2.62109C47.3471 2.62101 47.9253 2.80205 48.4073 3.13879C48.8893 3.47552 49.2511 3.95101 49.4422 4.49858L53.4007 15.8524H50.7067L49.7568 13.0926H43.7098L42.7213 15.8524H40.0078ZM44.484 10.7866H48.9809L47.3554 6.01714C47.1614 5.44722 46.3358 5.4452 46.139 6.0139L44.484 10.7866Z" fill="currentColor"></path><path d="M55.4336 9.23577C55.4336 5.51233 58.5151 2.46875 62.3336 2.46875C65.144 2.46875 67.4314 4.13241 68.5165 6.49493L66.0355 7.19459C65.338 5.85226 64.0585 4.88826 62.3336 4.88826C59.8526 4.88826 58.0306 6.81627 58.0306 9.23577C58.0306 11.6553 59.8542 13.5643 62.3336 13.5643C64.0585 13.5643 65.299 12.6949 65.9775 11.3339L68.497 11.9956C67.431 14.3399 65.1635 15.9838 62.3336 15.9838C58.5151 15.9838 55.4336 12.9608 55.4336 9.23577Z" fill="currentColor"></path><path d="M75.4167 15.8524V4.98361H71.1523V2.62109H82.1227V4.98361H78.0138V15.8524H75.4167Z" fill="currentColor"></path><path d="M84.7821 9.14791C84.8414 5.43538 87.9163 2.46657 91.7231 2.4884C95.5221 2.51063 98.5816 5.52637 98.6007 9.25547C98.6197 12.9846 95.4997 16.0055 91.6812 16.0055C87.8263 16.0035 84.722 12.9211 84.7821 9.14791ZM95.9842 9.25547C95.9842 6.83596 94.1606 4.84975 91.6812 4.84975C89.2198 4.84975 87.3783 6.83434 87.3783 9.25547C87.3783 11.656 89.2019 13.6208 91.6812 13.6208C94.1606 13.6208 95.9842 11.675 95.9842 9.25547Z" fill="currentColor"></path><path d="M102.145 15.8524V2.62109H108.25C110.925 2.62109 112.94 4.70027 112.94 7.10078C112.938 7.95978 112.666 8.79743 112.16 9.50052C111.654 10.2037 110.939 10.7383 110.111 11.0324L113.134 15.8524H110.169L107.358 11.3537H104.763V15.8524H102.145ZM104.761 9.14277H108.211C109.452 9.14277 110.421 8.25354 110.421 7.026C110.421 5.83525 109.509 4.90883 108.25 4.90883H104.763L104.761 9.14277Z" fill="currentColor"></path><path d="M119.726 11.7126L115.016 2.62109H117.788L121.005 8.83963L124.222 2.62109H126.994L122.342 11.6371V15.8524H119.726V11.7126Z" fill="currentColor"></path><path d="M13.9062 3.20484C13.8706 3.19623 13.8373 3.18019 13.8086 3.15788C13.7799 3.13552 13.7565 3.10743 13.74 3.07546C13.7234 3.04349 13.7142 3.00841 13.7128 2.97263C13.7115 2.93682 13.7181 2.90121 13.7322 2.86815C14.2188 1.71337 14.4334 0.789376 14.087 0.402562C13.1693 -0.623688 9.48933 1.41705 8.31598 2.10822C8.28457 2.12665 8.24942 2.13825 8.21299 2.14222C8.17656 2.14618 8.13967 2.14242 8.10486 2.13122C8.07004 2.12003 8.03809 2.10163 8.01123 2.0773C7.98437 2.05297 7.96323 2.02326 7.94918 1.99024C7.45597 0.83788 6.93748 0.036362 6.41194 0.00160127C5.01894 -0.0913635 3.89616 3.88951 3.56749 5.18697C3.5587 5.22173 3.54233 5.25423 3.5195 5.2822C3.49662 5.31021 3.46781 5.33305 3.43507 5.34918C3.40233 5.3653 3.36639 5.37432 3.32971 5.37561C3.29307 5.37694 3.25656 5.37052 3.22266 5.35677C2.03854 4.88225 1.09066 4.67288 0.694439 5.01078C-0.35788 5.90567 1.73432 9.49452 2.44305 10.6388C2.462 10.6694 2.47393 10.7037 2.47804 10.7392C2.48214 10.7748 2.47833 10.8108 2.46684 10.8447C2.45536 10.8787 2.43646 10.9099 2.41147 10.9361C2.38648 10.9623 2.35598 10.9828 2.32203 10.9965C1.14081 11.4775 0.318936 11.9831 0.282878 12.4956C0.187966 13.8541 4.26959 14.9491 5.60043 15.2696C5.63599 15.2783 5.66919 15.2943 5.69783 15.3167C5.72642 15.339 5.7498 15.3671 5.76625 15.399C5.78275 15.4309 5.79199 15.4659 5.79332 15.5016C5.79469 15.5373 5.78814 15.5729 5.77409 15.6059C5.28751 16.7607 5.07282 17.6851 5.41931 18.0715C6.33693 19.0977 10.0173 17.0574 11.1907 16.3662C11.2221 16.3477 11.2573 16.3361 11.2937 16.3321C11.3302 16.3281 11.3671 16.3318 11.4019 16.343C11.4368 16.3542 11.4687 16.3727 11.4955 16.397C11.5224 16.4214 11.5435 16.4511 11.5575 16.4842C12.0507 17.6362 12.5688 18.4377 13.0947 18.4729C14.4877 18.5654 15.6105 14.5849 15.9388 13.2871C15.9476 13.2524 15.9641 13.2199 15.987 13.192C16.0099 13.164 16.0388 13.1412 16.0716 13.1251C16.1043 13.1091 16.1403 13.1001 16.177 13.0988C16.2136 13.0975 16.2502 13.1039 16.284 13.1177C17.4681 13.5922 18.4156 13.8012 18.8122 13.4637C19.8646 12.5688 17.7719 8.97953 17.0632 7.83525C17.0444 7.80462 17.0326 7.77034 17.0286 7.73485C17.0245 7.69932 17.0284 7.66335 17.0399 7.62944C17.0514 7.59549 17.0702 7.56436 17.0951 7.53817C17.12 7.51198 17.1504 7.49129 17.1842 7.47758C18.3659 6.99659 19.1877 6.4909 19.2234 5.97838C19.3187 4.61989 15.2367 3.52497 13.9062 3.20484ZM12.3081 1.90249C12.5758 2.37055 11.1961 5.48935 10.1699 7.67079C10.1527 7.70725 10.1245 7.73772 10.0891 7.75809C10.0536 7.77847 10.0126 7.78776 9.97155 7.78473C9.93052 7.7817 9.8914 7.76646 9.85952 7.74112C9.82761 7.71573 9.80444 7.68146 9.79313 7.64286C9.37866 6.22454 8.90493 4.55809 8.39805 3.14341C8.37815 3.08787 8.37915 3.02724 8.40087 2.97239C8.42258 2.9175 8.46361 2.87195 8.51658 2.84386C9.78235 2.16966 11.9483 1.27437 12.3081 1.90249ZM6.24201 2.28849C6.77045 2.43481 8.05612 5.59161 8.91198 7.84176C8.92628 7.87935 8.92839 7.9203 8.91811 7.95914C8.90779 7.99794 8.88558 8.03274 8.85441 8.0589C8.8232 8.08505 8.78457 8.10126 8.74367 8.10534C8.70276 8.10946 8.66156 8.10126 8.62559 8.08185C7.30304 7.36603 5.76082 6.51318 4.37652 5.86242C4.32231 5.83676 4.27921 5.79322 4.25483 5.73947C4.23046 5.68575 4.22644 5.62532 4.24348 5.56898C4.65089 4.22058 5.53204 2.09246 6.24201 2.28849ZM2.23251 6.74474C2.71204 6.48363 5.91044 7.82923 8.14688 8.83002C8.18431 8.84675 8.21556 8.87424 8.23645 8.90884C8.25734 8.94339 8.26687 8.98341 8.26376 9.02343C8.26061 9.06344 8.24503 9.10156 8.219 9.13268C8.19301 9.16376 8.15787 9.1864 8.11828 9.19743C6.66435 9.60162 4.95511 10.0636 3.50449 10.558C3.44763 10.5772 3.38554 10.5762 3.32938 10.555C3.27322 10.5339 3.22655 10.4939 3.19779 10.4423C2.50771 9.2079 1.58802 7.09558 2.23251 6.74474ZM2.62832 12.6606C2.77794 12.1452 6.0153 10.8914 8.32261 10.0567C8.36116 10.0428 8.40319 10.0407 8.44297 10.0508C8.4828 10.0608 8.51849 10.0825 8.5453 10.1129C8.57208 10.1433 8.58874 10.181 8.59293 10.2209C8.59711 10.2607 8.5887 10.3009 8.56881 10.336C7.83438 11.6258 6.95986 13.1298 6.29258 14.4794C6.26651 14.5325 6.22187 14.5747 6.16671 14.5986C6.11158 14.6224 6.04954 14.6263 5.99168 14.6096C4.60903 14.2147 2.42689 13.353 2.62832 12.6606ZM7.19776 16.5707C6.92961 16.1031 8.30977 12.9839 9.33597 10.8029C9.35313 10.7664 9.38136 10.7359 9.41679 10.7155C9.45227 10.6952 9.49326 10.6859 9.53429 10.6889C9.57537 10.6919 9.61445 10.7072 9.64632 10.7325C9.67824 10.7579 9.7014 10.7922 9.71272 10.8308C10.1272 12.2487 10.6009 13.9156 11.1078 15.3303C11.1276 15.3858 11.1265 15.4463 11.1047 15.5011C11.0829 15.5559 11.0418 15.6014 10.9888 15.6294C9.7235 16.3023 7.5571 17.1993 7.19901 16.5707H7.19776ZM13.2638 16.1847C12.735 16.0388 11.4493 12.8817 10.5935 10.6315C10.5791 10.5938 10.5769 10.5528 10.5872 10.5139C10.5975 10.475 10.6198 10.4401 10.6511 10.414C10.6823 10.3878 10.7211 10.3716 10.762 10.3676C10.803 10.3635 10.8443 10.3719 10.8803 10.3914C12.2024 11.1072 13.745 11.9605 15.1289 12.6113C15.1832 12.6368 15.2264 12.6803 15.2508 12.7341C15.2752 12.7878 15.2792 12.8483 15.262 12.9047C14.855 14.2551 13.9738 16.3811 13.2638 16.1847ZM17.2733 11.7285C16.7934 11.99 13.5954 10.644 11.3586 9.64322C11.3211 9.62648 11.2899 9.599 11.269 9.5644C11.2481 9.52984 11.2386 9.48983 11.2417 9.44981C11.2448 9.40979 11.2604 9.37168 11.2864 9.34056C11.3124 9.30947 11.3476 9.28688 11.3871 9.27584C12.8415 8.87165 14.5503 8.40962 16.0009 7.91529C16.0579 7.89601 16.1201 7.89706 16.1763 7.91832C16.2326 7.93958 16.2793 7.97963 16.3081 8.03133C16.9977 9.26534 17.9174 11.378 17.2733 11.7285ZM16.8775 5.81266C16.7275 6.32842 13.4905 7.58227 11.1832 8.41693C11.1446 8.43092 11.1025 8.43302 11.0627 8.42299C11.0228 8.41293 10.987 8.39122 10.9602 8.36075C10.9334 8.33027 10.9168 8.29248 10.9126 8.2525C10.9085 8.21257 10.917 8.17231 10.937 8.13719C11.6711 6.84781 12.5456 5.3434 13.2129 3.99379C13.2391 3.94088 13.2837 3.8988 13.3389 3.87504C13.394 3.85127 13.456 3.84735 13.5138 3.86404C14.8964 4.26096 17.0785 5.12028 16.8775 5.81266Z" fill="currentColor"></path></svg>'

FACTORY_MARK = '<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 67 65"><title>Factory mark</title><path fill="currentColor" d="M47.75 11.15a.867.867 0 0 1-.671-.806.84.84 0 0 1 .067-.362c1.688-4.007 2.433-7.213 1.23-8.555-3.183-3.56-15.952 3.52-20.024 5.919a.9.9 0 0 1-1.273-.41c-1.711-3.998-3.51-6.78-5.334-6.9-4.833-.323-8.73 13.49-9.87 17.992a.85.85 0 0 1-.459.563.9.9 0 0 1-.737.027c-4.109-1.647-7.398-2.373-8.773-1.2-3.651 3.104 3.609 15.557 6.068 19.528a.85.85 0 0 1-.11 1.031.9.9 0 0 1-.31.21C3.455 39.856.604 41.61.478 43.389c-.329 4.713 13.834 8.513 18.452 9.625q.186.046.337.163a.87.87 0 0 1 .332.642.84.84 0 0 1-.067.362c-1.688 4.007-2.433 7.214-1.23 8.555 3.183 3.561 15.954-3.519 20.025-5.917a.9.9 0 0 1 1.058.107.9.9 0 0 1 .215.302c1.711 3.997 3.509 6.779 5.334 6.9 4.833.322 8.73-13.49 9.868-17.993a.85.85 0 0 1 .168-.33.88.88 0 0 1 .659-.324.9.9 0 0 1 .371.066c4.109 1.647 7.397 2.372 8.773 1.2 3.651-3.105-3.61-15.559-6.07-19.53a.85.85 0 0 1 .111-1.03.9.9 0 0 1 .31-.21c4.1-1.67 6.952-3.424 7.075-5.203.331-4.713-13.833-8.513-18.45-9.623m-5.546-4.518c.93 1.624-3.858 12.446-7.42 20.015a.7.7 0 0 1-.28.303.71.71 0 0 1-.796-.059.7.7 0 0 1-.23-.341c-1.439-4.921-3.082-10.704-4.841-15.612a.84.84 0 0 1 .01-.594.87.87 0 0 1 .401-.446c4.392-2.34 11.908-5.446 13.156-3.266m-21.048 1.34c1.833.507 6.294 11.46 9.264 19.268a.67.67 0 0 1-.2.754.71.71 0 0 1-.794.08c-4.589-2.485-9.94-5.444-14.743-7.702a.87.87 0 0 1-.422-.427.84.84 0 0 1-.04-.591c1.414-4.679 4.471-12.063 6.935-11.383M7.243 23.433c1.664-.906 12.762 3.763 20.522 7.235.13.058.239.154.311.274a.67.67 0 0 1-.06.776.7.7 0 0 1-.35.225c-5.045 1.403-10.976 3.006-16.01 4.721a.9.9 0 0 1-.607-.01.88.88 0 0 1-.456-.391c-2.395-4.284-5.586-11.613-3.35-12.83M8.617 43.96c.519-1.788 11.752-6.14 19.758-9.035a.72.72 0 0 1 .773.195.67.67 0 0 1 .081.774c-2.548 4.475-5.582 9.694-7.898 14.377a.87.87 0 0 1-.437.413.9.9 0 0 1-.607.039c-4.797-1.37-12.37-4.36-11.67-6.763m15.855 13.568c-.93-1.623 3.859-12.446 7.42-20.014a.7.7 0 0 1 .28-.303.715.715 0 0 1 .796.059.7.7 0 0 1 .23.34c1.439 4.92 3.083 10.705 4.841 15.613a.84.84 0 0 1-.01.593.87.87 0 0 1-.402.445c-4.391 2.335-11.908 5.447-13.15 3.267zm21.049-1.34c-1.836-.506-6.297-11.461-9.266-19.269a.67.67 0 0 1 .2-.755.71.71 0 0 1 .795-.078c4.587 2.484 9.94 5.445 14.742 7.703.189.088.339.24.423.426a.84.84 0 0 1 .039.592c-1.413 4.686-4.47 12.063-6.933 11.381m13.912-15.462c-1.665.907-12.762-3.763-20.523-7.236a.7.7 0 0 1-.311-.273.67.67 0 0 1 .06-.777.7.7 0 0 1 .35-.225c5.046-1.402 10.975-3.005 16.009-4.72a.9.9 0 0 1 .609.01.88.88 0 0 1 .457.392c2.393 4.282 5.584 11.613 3.349 12.829M58.06 20.2c-.521 1.79-11.753 6.14-19.759 9.036a.72.72 0 0 1-.774-.195.67.67 0 0 1-.08-.776c2.547-4.474 5.581-9.694 7.897-14.377a.87.87 0 0 1 .437-.412.9.9 0 0 1 .607-.038c4.797 1.377 12.37 4.359 11.672 6.762"></path></svg>'



def format_money(amount: float, currency: str = "USD", decimals: int = 0) -> str:
    symbol = CURRENCY_SYMBOLS[currency]
    # Round before taking the sign so tiny negatives don't display as "-£0".
    rounded = round(amount, decimals)
    sign = "-" if rounded < 0 else ""
    return f"{sign}{symbol}{abs(rounded):,.{decimals}f}"


def format_percent(value: float) -> str:
    # Round halves away from zero (187.5 -> 188, 12.5 -> 13), as a reader checking by
    # hand would; Python's round() would give 12. int() also turns -0 into 0.
    rounded = decimal.Decimal(value).quantize(decimal.Decimal(1), decimal.ROUND_HALF_UP)
    return f"{int(rounded):,}%"


def format_number(value: float) -> str:
    if float(value).is_integer():
        return f"{value:,.0f}"
    return f"{value:,.6f}".rstrip("0").rstrip(".")


def format_adoption(value: float) -> str:
    return f"{format_number(value)}%"


def format_ramp(ramp: Sequence[float], separator: str = " / ") -> str:
    return separator.join(format_adoption(v) for v in ramp)


def format_ramp_words(ramp: Sequence[float]) -> str:
    first, second, third = (format_adoption(v) for v in ramp)
    return f"{first}, {second} and {third}"


def format_payback(payback_months: float,
                   never: str = "Does not pay back (value does not exceed cost)") -> str:
    if math.isinf(payback_months):
        return never
    return f"{payback_months:.1f} months"


def format_first_year_payback(result: RoiResult) -> str:
    return format_payback(result.first_year_payback_months,
                          "Does not pay back in year one")


def summary_rows(result: RoiResult, currency: str = "USD"):
    return [
        ("Engineer hourly cost", format_money(result.hourly_cost, currency, 2)),
        ("Hours saved per year", f"{result.hours_saved_per_year:,.0f}"),
        ("Estimated value of time saved", format_money(result.annual_value, currency)),
        ("Annual tool cost", format_money(result.annual_cost, currency)),
        ("Estimated net annual value", format_money(result.net_value, currency)),
        ("Annual ROI at full adoption", format_percent(result.roi_percent)),
        ("Payback at full adoption", format_payback(result.payback_months)),
    ]


def three_year_summary_rows(result: RoiResult):
    return [
        ("Three-year ROI", format_percent(result.three_year_roi_percent)),
        ("Payback in year one", format_first_year_payback(result)),
    ]


def _num_attr(value) -> str:
    """Exact value for a form field, so the browser can parse it back."""
    if isinstance(value, int):
        return str(value)
    return f"{value:.10g}"


def _field(field_id: str, label: str, value, extra: str = "") -> str:
    return (f'<tr><th><label for="{field_id}">{html.escape(label)}</label></th>'
            f'<td><input id="{field_id}" type="number" step="any"{extra} '
            f'value="{_num_attr(value)}"></td></tr>')


def _inputs_form(customer: str, result: RoiResult, currency: str) -> str:
    name = html.escape(customer, quote=True)
    rows = [
        f'<tr><th><label for="in-customer">Customer name</label></th>'
        f'<td><input id="in-customer" type="text" value="{name}"></td></tr>',
        _field("in-engineers", "Engineers", result.engineers, ' min="1"'),
        _field("in-loaded-cost", "Fully loaded annual cost per engineer",
               result.loaded_annual_cost, ' min="0"'),
        _field("in-hours-saved", "Hours saved per engineer per week",
               result.hours_saved_per_week, ' min="0"'),
        _field("in-weeks", "Working weeks per year", result.working_weeks,
               ' min="1" max="52"'),
        _field("in-hours-week", "Hours per working week", result.hours_per_week,
               ' min="0"'),
        _field("in-tool-cost", "Annual tool cost", result.annual_cost, ' min="0"'),
    ]
    ramp_inputs = "".join(
        f'<input id="in-ramp{i}" class="ramp" type="number" step="any" '
        f'min="0" max="100" value="{_num_attr(v)}">'
        for i, v in enumerate(result.ramp, start=1))
    rows.append(f'<tr><th>Adoption ramp (years 1–3)</th><td>{ramp_inputs}</td></tr>')
    options = "".join(
        f'<option value="{code}"{" selected" if code == currency else ""}>'
        f'{code} ({CURRENCY_SYMBOLS[code]})</option>'
        for code in sorted(CURRENCY_SYMBOLS))
    rows.append('<tr><th><label for="in-currency">Currency</label></th>'
                f'<td><select id="in-currency">{options}</select></td></tr>')
    return ('<form id="inputs-form">\n<table class="inputs">\n' + "\n".join(rows) +
            "\n</table>\n</form>\n"
            '<p id="input-error" role="alert" hidden>Some inputs are invalid '
            '(highlighted in red), so the figures are unchanged.</p>\n'
            '<p id="week-warning" hidden></p>\n'
            '<p class="note"><strong>This report is interactive:</strong> edit any '
            'input above and every figure on the page updates instantly, entirely in '
            'your browser. Nothing you type is sent anywhere.</p>')


# Recalculates every figure on the page when an input changes. It mirrors
# calculate_roi and the format_* helpers above; keep the two in sync.
_REPORT_SCRIPT = r"""<script>
(function () {
  "use strict";
  var SYM = { USD: "$", GBP: "£", EUR: "€" };

  function el(id) { return document.getElementById(id); }

  function grouped(intPart) {
    return intPart.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  }

  function fmtMoney(x, sym, decimals) {
    var scale = Math.pow(10, decimals);
    var r = Math.round(x * scale) / scale;
    var sign = r < 0 ? "-" : "";
    var parts = Math.abs(r).toFixed(decimals).split(".");
    parts[0] = grouped(parts[0]);
    return sign + sym + parts.join(".");
  }

  function fmtPercent(x) {
    // Halves round away from zero, and -0 becomes 0, as in format_percent.
    var r = (x < 0 ? -1 : 1) * Math.round(Math.abs(x));
    return grouped(String(r)) + "%";
  }

  function fmtNumber(x) {
    var neg = x < 0 ? "-" : "";
    var a = Math.abs(x);
    var s;
    if (Number.isInteger(a)) {
      s = String(a);
    } else {
      s = a.toFixed(6).replace(/0+$/, "").replace(/\.$/, "");
    }
    var parts = s.split(".");
    parts[0] = grouped(parts[0]);
    return neg + parts.join(".");
  }

  function fmtAdoption(x) { return fmtNumber(x) + "%"; }

  function fmtPayback(months, neverText) {
    if (!isFinite(months)) return neverText;
    return months.toFixed(1) + " months";
  }

  function field(id) { return parseFloat(el(id).value); }

  function mark(id, ok) {
    el(id).classList.toggle("invalid", !ok);
    return ok;
  }

  function findByPrefix(selector, prefix) {
    var nodes = document.querySelectorAll(selector);
    for (var i = 0; i < nodes.length; i++) {
      if (nodes[i].textContent.indexOf(prefix) === 0) return nodes[i];
    }
    return null;
  }

  function recalc() {
    var engineers = field("in-engineers");
    var loaded = field("in-loaded-cost");
    var hours = field("in-hours-saved");
    var tool = field("in-tool-cost");
    var weeks = field("in-weeks");
    var hpw = field("in-hours-week");
    var ramp = [field("in-ramp1"), field("in-ramp2"), field("in-ramp3")];

    var ok = true;
    ok = mark("in-engineers", isFinite(engineers) && engineers > 0) && ok;
    ok = mark("in-loaded-cost", isFinite(loaded) && loaded > 0) && ok;
    ok = mark("in-hours-saved", isFinite(hours) && hours >= 0 && hours <= hpw) && ok;
    ok = mark("in-tool-cost", isFinite(tool) && tool > 0) && ok;
    ok = mark("in-weeks", isFinite(weeks) && weeks >= 1 && weeks <= 52) && ok;
    ok = mark("in-hours-week", isFinite(hpw) && hpw > 0) && ok;
    for (var i = 0; i < 3; i++) {
      ok = mark("in-ramp" + (i + 1),
                isFinite(ramp[i]) && ramp[i] >= 0 && ramp[i] <= 100) && ok;
    }
    var err = el("input-error");
    if (!ok) { err.hidden = false; return; }

    var hourly = loaded / (weeks * hpw);
    var hoursYear = engineers * hours * weeks;
    var annualValue = hoursYear * hourly;
    var net = annualValue - tool;
    var roi = net / tool * 100;
    var years = [];
    var cum = 0;
    var totalValue = 0;
    for (i = 0; i < 3; i++) {
      var yv = annualValue * ramp[i] / 100;
      var yn = yv - tool;
      cum += yn;
      totalValue += yv;
      years.push({ adoption: ramp[i], value: yv, net: yn, cum: cum });
    }
    var totalCost = tool * 3;
    var totalNet = totalValue - totalCost;
    var threeRoi = totalNet / totalCost * 100;
    if (![hourly, annualValue, net, roi, totalValue, totalCost, totalNet, threeRoi]
        .every(isFinite)) { err.hidden = false; return; }
    err.hidden = true;

    var code = el("in-currency").value;
    var sym = SYM[code];
    var money = function (x) { return fmtMoney(x, sym, 0); };

    var customer = el("in-customer").value.trim() || "Prospect";
    document.title = "ROI estimate for " + customer;
    document.querySelector("h1").textContent = "AI agent ROI estimate: " + customer;

    document.querySelector(".big").textContent = fmtPercent(threeRoi) + " three-year ROI";
    var sub = "Adoption by year: " + ramp.map(fmtAdoption).join(" → ") + ". ";
    if (ramp[2] === 100) {
      sub += "At full adoption: " + fmtPercent(roi) + " a year.";
    } else {
      sub += "Full adoption is not reached; at 100% the annual ROI would be " +
        fmtPercent(roi) + ".";
    }
    document.querySelector(".sub").textContent = sub;

    var body = "";
    for (i = 0; i < 3; i++) {
      body += "<tr><th>Year " + (i + 1) + "</th><td>" + fmtAdoption(years[i].adoption) +
        "</td><td>" + money(years[i].value) + "</td><td>" + money(tool) + "</td><td>" +
        money(years[i].net) + "</td><td>" + money(years[i].cum) + "</td></tr>";
    }
    body += '<tr class="total"><th>Total</th><td></td><td>' + money(totalValue) +
      "</td><td>" + money(totalCost) + "</td><td>" + money(totalNet) +
      "</td><td></td></tr>";
    document.querySelector("table.three-year tbody").innerHTML = body;

    var yearOnePayback = years[0].value > tool ? tool / (years[0].value / 12) : Infinity;
    document.querySelector("table.three-year-summary").innerHTML =
      "<tr><th>Three-year ROI</th><td>" + fmtPercent(threeRoi) + "</td></tr>" +
      "<tr><th>Payback in year one</th><td>" +
      fmtPayback(yearOnePayback, "Does not pay back in year one") + "</td></tr>";

    var payback = annualValue > tool ? tool / (annualValue / 12) : Infinity;
    document.querySelector("table.results").innerHTML =
      "<tr><th>Engineer hourly cost</th><td>" + fmtMoney(hourly, sym, 2) + "</td></tr>" +
      "<tr><th>Hours saved per year</th><td>" + grouped(String(Math.round(hoursYear))) +
      "</td></tr>" +
      "<tr><th>Estimated value of time saved</th><td>" + money(annualValue) +
      "</td></tr>" +
      "<tr><th>Annual tool cost</th><td>" + money(tool) + "</td></tr>" +
      "<tr><th>Estimated net annual value</th><td>" + money(net) + "</td></tr>" +
      "<tr><th>Annual ROI at full adoption</th><td>" + fmtPercent(roi) + "</td></tr>" +
      "<tr><th>Payback at full adoption</th><td>" +
      fmtPayback(payback, "Does not pay back (value does not exceed cost)") +
      "</td></tr>";

    var heading = findByPrefix("h2", "At full adoption");
    if (heading) {
      heading.textContent = ramp[2] === 100 ? "At full adoption (year 3 onwards)" :
        "At full adoption (100%)";
    }

    var note = findByPrefix("p.note", "All amounts are in");
    if (note) {
      note.textContent = "All amounts are in " + code + " (" + sym +
        "). No exchange-rate conversion is applied.";
    }

    var caveat = findByPrefix("ul.caveats li", "The three-year view assumes adoption of");
    if (caveat) {
      caveat.textContent = "The three-year view assumes adoption of " +
        fmtAdoption(ramp[0]) + ", " + fmtAdoption(ramp[1]) + " and " +
        fmtAdoption(ramp[2]) + " in years one to three. The full-adoption figures " +
        "assume no ramp-up, so they are a best case.";
    }

    var warn = el("week-warning");
    if (hours > 0.2 * hpw) {
      var share = Math.round(hours / hpw * 1000) / 10;
      warn.textContent = "Warning: hours saved per week (" + fmtNumber(hours) + ") is " +
        fmtNumber(share) + "% of a " + fmtNumber(hpw) +
        "-hour week. A customer may see this as unrealistic; double-check it " +
        "before sharing.";
      warn.hidden = false;
    } else {
      warn.hidden = true;
    }
  }

  var form = el("inputs-form");
  form.addEventListener("input", recalc);
  form.addEventListener("change", recalc);
  form.addEventListener("submit", function (event) { event.preventDefault(); });
  recalc();
})();
</script>"""


ROUNDING_NOTE = (
    "Figures are rounded for display. Totals are calculated from unrounded values, "
    "so displayed figures may not multiply or add up exactly."
)


def full_adoption_heading(result: RoiResult) -> str:
    if result.ramp[2] == 100:
        return "At full adoption (year 3 onwards)"
    return "At full adoption (100%)"


def headline_subline(result: RoiResult) -> str:
    ramp = f"Adoption by year: {format_ramp(result.ramp, ' → ')}."
    full = format_percent(result.roi_percent)
    if result.ramp[2] == 100:
        return f"{ramp} At full adoption: {full} a year."
    return f"{ramp} Full adoption is not reached; at 100% the annual ROI would be {full}."


def caveats(result: RoiResult) -> Tuple[str, ...]:
    return (
        "It assumes every hour saved becomes productive work.",
        f"The three-year view assumes adoption of {format_ramp_words(result.ramp)} in "
        "years one to three. The full-adoption figures assume no ramp-up, so they are "
        "a best case.",
        "It treats the tool cost as recurring every year, paid at the start of each "
        "year, at the full price even while adoption ramps up.",
        "Three-year figures are simple totals; they are not discounted for the time "
        "value of money.",
        "It excludes implementation, training and review costs.",
    )


def _aligned(rows) -> str:
    width = max(len(label) for label, _ in rows) + 2
    return "\n".join(f"{label + ':':<{width}}{value}" for label, value in rows)


def format_summary(result: RoiResult, currency: str = "USD") -> str:
    return _aligned(summary_rows(result, currency))


def format_three_year(result: RoiResult, currency: str = "USD") -> str:
    money = lambda amount: format_money(amount, currency)  # noqa: E731
    rows = [
        (f"Year {y.year} at {format_adoption(y.adoption_percent)} adoption",
         f"value {money(y.value)}, cost {money(y.cost)}, net {money(y.net)}, "
         f"cumulative net {money(y.cumulative_net)}")
        for y in result.years
    ]
    rows.append(("Three-year total",
                 f"value {money(result.three_year_value)}, "
                 f"cost {money(result.three_year_cost)}, "
                 f"net {money(result.three_year_net)}"))
    rows.extend(three_year_summary_rows(result))
    heading = (f"Three-year view (adoption {format_ramp(result.ramp, ' → ')}, "
               "tool cost fixed each year)")
    return f"{heading}\n{_aligned(rows)}"


def _table_rows(rows) -> str:
    return "".join(
        f"<tr><th>{html.escape(label)}</th><td>{html.escape(value)}</td></tr>"
        for label, value in rows
    )


def _three_year_table(result: RoiResult, currency: str) -> str:
    def cells(values):
        return "".join(f"<td>{html.escape(v)}</td>" for v in values)

    money = lambda amount: format_money(amount, currency)  # noqa: E731
    head = "".join(f"<th>{h}</th>" for h in (
        "Year", "Adoption", "Estimated value of time saved", "Tool cost", "Net",
        "Cumulative net"))
    body = "".join(
        f"<tr><th>Year {y.year}</th>"
        + cells((format_adoption(y.adoption_percent), money(y.value), money(y.cost),
                 money(y.net), money(y.cumulative_net)))
        + "</tr>"
        for y in result.years
    )
    total = ('<tr class="total"><th>Total</th>'
             + cells(("", money(result.three_year_value), money(result.three_year_cost),
                      money(result.three_year_net), ""))
             + "</tr>")
    return (f'<table class="three-year"><thead><tr>{head}</tr></thead>'
            f"<tbody>{body}{total}</tbody></table>")


def render_html(customer: str, result: RoiResult, currency: str = "USD") -> str:
    three_year = _three_year_table(result, currency)
    three_year_summary = _table_rows(three_year_summary_rows(result))
    rows = _table_rows(summary_rows(result, currency))
    form = _inputs_form(customer, result, currency)
    currency_note = html.escape(
        f"All amounts are in {currency} ({CURRENCY_SYMBOLS[currency]}). "
        "No exchange-rate conversion is applied."
    )
    caveat_items = "".join(f"<li>{html.escape(c)}</li>" for c in caveats(result))
    headline = html.escape(format_percent(result.three_year_roi_percent))
    subline = html.escape(headline_subline(result))
    full_heading = html.escape(full_adoption_heading(result))
    name = html.escape(customer)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>ROI estimate for {name}</title>
<style>
  body {{ font-family: -apple-system, Helvetica, Arial, sans-serif; max-width: 720px;
         margin: 48px auto; color: #1c1917; }}
  h1 {{ font-size: 24px; margin-bottom: 4px; }}
  h2 {{ font-size: 18px; margin: 40px 0 0; }}
  p {{ color: #57534e; margin-top: 0; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 24px; }}
  th, td {{ padding: 12px 8px; border-bottom: 1px solid #e7e5e4; text-align: left; }}
  td {{ text-align: right; font-variant-numeric: tabular-nums; font-weight: 600; }}
  .three-year {{ font-size: 14px; }}
  .three-year thead th {{ text-align: right; color: #57534e; font-weight: 600; }}
  .three-year thead th:first-child {{ text-align: left; }}
  .three-year td {{ font-weight: 400; }}
  .three-year .total th, .three-year .total td {{ font-weight: 700;
         border-top: 2px solid #1c1917; }}
  table.inputs input, table.inputs select {{ font: inherit; font-weight: 400;
         padding: 4px 6px; border: 1px solid #d6d3d1; border-radius: 6px;
         width: 120px; text-align: right; }}
  table.inputs input[type="text"] {{ width: 240px; text-align: left; }}
  table.inputs input.ramp {{ width: 64px; margin-right: 6px; }}
  table.inputs input.invalid {{ border-color: #dc2626; background: #fef2f2; }}
  #input-error {{ color: #b91c1c; font-weight: 600; }}
  #week-warning {{ background: #fffbeb; border: 1px solid #f59e0b; border-radius: 6px;
         padding: 10px 14px; color: #92400e; }}
  .brand {{ display: flex; justify-content: space-between; align-items: center;
         margin-bottom: 40px; padding-bottom: 16px;
         border-bottom: 1px solid #e7e5e4; }}
  .brand svg {{ height: 19px; width: auto; color: #1c1917; display: block; }}
  .brand-tag {{ font-size: 13px; color: #57534e; letter-spacing: 0.08em;
         text-transform: uppercase; }}
  .built {{ margin-top: 56px; padding-top: 16px; border-top: 1px solid #e7e5e4;
         display: flex; align-items: center; gap: 8px; font-size: 13px;
         color: #57534e; }}
  .built svg {{ height: 16px; width: auto; }}
  .built a {{ color: inherit; }}
  .big {{ font-size: 40px; font-weight: 700; color: #ea580c; margin: 24px 0 0; }}
  .sub {{ font-size: 15px; margin-top: 4px; }}
  .note {{ font-size: 14px; margin-top: 12px; }}
  ul {{ color: #57534e; padding-left: 20px; }}
  li {{ margin: 6px 0; }}
</style>
</head>
<body>
<header class="brand">{FACTORY_WORDMARK}<span class="brand-tag">ROI estimate</span></header>
<h1>AI agent ROI estimate: {name}</h1>
<p>Illustrative estimate. Results depend entirely on the inputs used.</p>
<div class="big">{headline} three-year ROI</div>
<p class="sub">{subline}</p>
<h2>Three-year view</h2>
{three_year}
<table class="three-year-summary">{three_year_summary}</table>
<h2>{full_heading}</h2>
<table class="results">{rows}</table>
<p class="note">{html.escape(ROUNDING_NOTE)}</p>
<h2>Inputs and assumptions</h2>
{form}
<p class="note">{currency_note}</p>
<h2>Caveats</h2>
<p>This is an estimate, not a forecast.</p>
<ul class="caveats">{caveat_items}</ul>
<footer class="built">{FACTORY_MARK}<span>Produced with Factory Droid &middot; <a href="https://factory.ai">factory.ai</a></span></footer>
{_REPORT_SCRIPT}
</body>
</html>
"""


HELP_EXAMPLE = ('python3 roi.py --customer "Acme Bank UK" --engineers 100 '
                '--loaded-cost 150000 --hours-saved 4 --tool-cost 400000 --currency GBP')


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=f"example:\n  {HELP_EXAMPLE}",
        # Keeps the example on one line so it can be copied and run as-is.
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--customer", default="Prospect",
                        help='Customer name shown on the report (default "Prospect")')
    parser.add_argument("--engineers", type=int, required=True,
                        help="Number of engineers using the tool")
    parser.add_argument("--loaded-cost", type=float, required=True,
                        help="Fully loaded annual cost per engineer, in the chosen --currency")
    parser.add_argument("--hours-saved", type=float, required=True,
                        help="Hours saved per engineer per week")
    parser.add_argument("--tool-cost", type=float, required=True,
                        help="Annual cost of the tool, in the chosen --currency")
    parser.add_argument("--weeks", type=int, default=46,
                        help="Working weeks per year, from 1 to 52 (default 46)")
    parser.add_argument("--ramp", default="50,80,100",
                        help="Adoption percentages for years one, two and three, "
                             "separated by commas (default 50,80,100)")
    parser.add_argument("--currency", choices=sorted(CURRENCY_SYMBOLS), default="USD",
                        help="Currency for all money inputs and outputs. "
                             "Labels only: no exchange-rate conversion is applied.")
    parser.add_argument("--html", metavar="PATH", help="Also write an HTML report")
    args = parser.parse_args(argv)

    customer = args.customer.strip() or "Prospect"

    try:
        ramp = parse_ramp(args.ramp)
        result = calculate_roi(args.engineers, args.loaded_cost, args.hours_saved,
                               args.tool_cost, working_weeks=args.weeks, ramp=ramp)
    except ValueError as exc:
        parser.error(str(exc))

    if result.hours_saved_per_week > 0.2 * result.hours_per_week:
        share = result.hours_saved_per_week / result.hours_per_week * 100
        print(f"Warning: --hours-saved {result.hours_saved_per_week:g} is "
              f"{round(share, 1):g}% "
              f"of a {result.hours_per_week:g}-hour week. A customer may see this as "
              "unrealistic; double-check it before sharing.", file=sys.stderr)

    # Write the report before printing so a bad path fails cleanly, not mid-output.
    if args.html is not None and not args.html.strip():
        parser.error("--html needs a file path, for example --html report.html")
    if args.html is not None:
        # Render first so a rendering error can't leave an empty file behind.
        page = render_html(customer, result, args.currency)
        try:
            with open(args.html, "w", encoding="utf-8") as f:
                f.write(page)
        except OSError as exc:
            parser.error(f"could not write HTML report to {args.html}: "
                         f"{exc.strerror or exc}")

    print(f"ROI estimate for {customer}\n")
    print(format_three_year(result, args.currency))
    print()
    print(full_adoption_heading(result))
    print(format_summary(result, args.currency))
    print(f"\n{ROUNDING_NOTE}")
    print("Estimate only: it assumes every hour saved becomes productive work and "
          f"adoption of {format_ramp_words(result.ramp)} in years one to three. "
          "Use --html for the full inputs and caveats.")
    if args.html is not None:
        print(f"\nHTML report written to {args.html}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

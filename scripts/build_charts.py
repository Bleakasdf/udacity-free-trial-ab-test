from pathlib import Path

import pandas as pd
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "charts"
OUT.mkdir(parents=True, exist_ok=True)
BLUE, ORANGE, INK, GRID, WHITE = "#2F6B9A", "#D9892B", "#172B4D", "#D9E2EC", "#FFFFFF"


def font(size=24, bold=False):
    name = "seguisb.ttf" if bold else "segoeui.ttf"
    return ImageFont.truetype(str(Path("C:/Windows/Fonts") / name), size)


def funnel_chart():
    data = pd.read_csv(ROOT / "data" / "powerbi" / "funnel.csv")
    stages = ["Page view", "Start trial click", "Free-trial enrollment", "Payment"]
    image = Image.new("RGB", (1400, 720), WHITE)
    draw = ImageDraw.Draw(image)
    draw.text((70, 35), "Mature funnel by experiment group", fill=INK, font=font(34, True))
    left, top, width = 300, 130, 1000
    maximum = data.users.max()
    for i, stage in enumerate(stages):
        y = top + i * 135
        draw.text((70, y + 25), stage, fill=INK, font=font(23))
        for j, group in enumerate(["Control", "Experiment"]):
            value = int(data[(data.stage == stage) & (data.experiment_group == group)].users.iloc[0])
            bar_width = int(width * value / maximum)
            color = BLUE if group == "Control" else ORANGE
            yy = y + j * 48
            draw.rounded_rectangle((left, yy, left + bar_width, yy + 34), radius=5, fill=color)
            draw.text((left + bar_width + 12, yy), f"{value:,}", fill=INK, font=font(20))
    draw.rectangle((930, 55, 955, 80), fill=BLUE); draw.text((965, 53), "Control", fill=INK, font=font(20))
    draw.rectangle((1100, 55, 1125, 80), fill=ORANGE); draw.text((1135, 53), "Experiment", fill=INK, font=font(20))
    image.save(OUT / "mature_funnel.png")


def effect_chart():
    data = pd.read_csv(ROOT / "data" / "powerbi" / "metric_results.csv").iloc[:2]
    image = Image.new("RGB", (1400, 650), WHITE)
    draw = ImageDraw.Draw(image)
    draw.text((70, 35), "Estimated effects with 95% confidence intervals", fill=INK, font=font(34, True))
    x0, x1, low, high = 340, 1300, -0.035, 0.01
    scale = lambda value: x0 + int((value - low) / (high - low) * (x1 - x0))
    zero = scale(0)
    draw.line((zero, 120, zero, 540), fill="#667085", width=2)
    for tick in [-.03, -.02, -.01, 0, .01]:
        x = scale(tick)
        draw.line((x, 530, x, 545), fill=INK, width=2)
        draw.text((x - 25, 555), f"{tick:+.0%}", fill=INK, font=font(18))
    for i, row in data.reset_index(drop=True).iterrows():
        y = 230 + i * 190
        draw.text((70, y - 18), row.metric, fill=INK, font=font(25, True))
        draw.line((scale(row.ci_low), y, scale(row.ci_high), y), fill=BLUE, width=8)
        draw.ellipse((scale(row.difference)-11, y-11, scale(row.difference)+11, y+11), fill=BLUE)
        threshold = scale(row.practical_threshold)
        draw.line((threshold, y-55, threshold, y+55), fill=ORANGE, width=4)
        draw.text((scale(row.ci_high)+12, y-15), f"{row.difference:+.2%}", fill=INK, font=font(20))
    draw.text((70, 605), "Orange line = practical threshold", fill=ORANGE, font=font(18))
    image.save(OUT / "metric_effects.png")


funnel_chart()
effect_chart()
print(OUT)

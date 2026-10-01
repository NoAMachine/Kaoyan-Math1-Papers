#!/usr/bin/env python3
"""Split Math I papers into one Markdown file per question and classify by topic."""

from __future__ import annotations

import argparse
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path


# region Configuration

ROOT = Path(__file__).resolve().parents[1]
PAPERS_DIR = ROOT / "papers"
OUTPUT_DIR = ROOT / "knowledge"

SOURCE_OVERRIDES = {
    2022: ROOT / "solutions" / "2022年解析" / "2022年解析.md",
    2023: ROOT / "solutions" / "2023年解析" / "2023年解析.md",
    2024: PAPERS_DIR / "2024年数学(一)真题及参考答案.md",
}

TOPICS: dict[tuple[str, str], tuple[str, ...]] = {
    ("高等数学", "函数极限与连续"): ("极限", "无穷小", "连续", "间断", "洛必达", "lim_", "lim ", "定义域"),
    ("高等数学", "一元函数微分学"): ("导数", "微分", "中值定理", "单调", "极值", "最值", "极大值", "极小值", "拐点", "凹凸", "曲率", "渐近线", "切线", "可微", "f^{\\prime}"),
    ("高等数学", "一元函数积分学"): ("不定积分", "定积分", "反常积分", "变上限", "积分上限", "分部积分", "旋转体", "弧长", "\\int_"),
    ("高等数学", "向量代数与空间解析几何"): ("空间直角坐标系", "空间曲线", "平面方程", "直线方程", "方向向量", "法向量", "夹角", "距离"),
    ("高等数学", "多元函数微分学"): ("偏导", "全微分", "隐函数", "方向导数", "梯度", "条件极值", "拉格朗日", "切平面", "法线"),
    ("高等数学", "重积分"): ("二重积分", "三重积分", "积分区域", "积分次序", "极坐标", "柱坐标", "球坐标", "形心", "\\iint", "\\iiint"),
    ("高等数学", "曲线积分与曲面积分"): ("曲线积分", "曲面积分", "格林", "高斯公式", "斯托克斯", "路径无关", "通量", "向量场", "\\oint"),
    ("高等数学", "无穷级数"): ("级数", "收敛半径", "收敛域", "和函数", "傅里叶", "\\sum_"),
    ("高等数学", "常微分方程"): ("微分方程", "通解", "初始条件", "可分离变量", "伯努利", "欧拉方程"),
    ("线性代数", "行列式"): ("行列式", "余子式", "克拉默"),
    ("线性代数", "矩阵"): ("矩阵", "逆矩阵", "伴随矩阵", "初等变换", "分块矩阵", "矩阵方程", "\\mathbf{a}", "\\pmb{a}"),
    ("线性代数", "向量组"): ("向量组", "线性相关", "线性无关", "线性表示", "极大无关组", "向量空间", "一组基"),
    ("线性代数", "线性方程组"): ("线性方程组", "齐次方程组", "非齐次方程组", "基础解系", "增广矩阵", "同解"),
    ("线性代数", "特征值与特征向量"): ("特征值", "特征向量", "特征方程", "相似矩阵", "相似于", "对角化", "实对称矩阵"),
    ("线性代数", "二次型"): ("二次型", "合同", "标准形", "规范形", "惯性指数", "正定"),
    ("概率论与数理统计", "随机事件与概率"): ("随机事件", "条件概率", "全概率", "贝叶斯", "事件独立", "独立试验", "古典概型", "几何概型", "概率", "箱子", "命中率"),
    ("概率论与数理统计", "一维随机变量及其分布"): ("分布函数", "概率密度", "概率分布", "二项分布", "泊松分布", "均匀分布", "指数分布", "正态分布"),
    ("概率论与数理统计", "多维随机变量及其分布"): ("二维随机变量", "联合分布", "联合密度", "边缘分布", "边缘密度", "条件分布", "二维正态"),
    ("概率论与数理统计", "随机变量的数字特征"): ("数学期望", "期望", "方差", "协方差", "相关系数", "不相关", "E(", "D("),
    ("概率论与数理统计", "大数定律与中心极限定理"): ("切比雪夫", "大数定律", "中心极限定理", "独立同分布", "依概率收敛", "正态近似"),
    ("概率论与数理统计", "数理统计"): ("总体", "简单随机样本", "样本均值", "样本方差", "统计量", "抽样分布", "矩估计", "最大似然", "无偏估计", "置信区间", "假设检验"),
}

SECTION_RE = re.compile(r"^(?:#\s*)?([一二三四五六七八九十]+)、([^\n]*)$", re.M)
NUMBER_RE = re.compile(
    r"^(?:#\s*)?\s*(?:"
    r"\(\s*(\d{1,2})\s*\)|（\s*(\d{1,2})\s*）|"
    r"【\s*(\d{1,2})\s*】|(\d{1,2})\s*[.．、）)]|"
    r"(\d{1,2})\s+(?=[\u4e00-\u9fff$]))\s*",
    re.M,
)
ANSWER_RE = re.compile(r"(?m)^\s*(?:【|〖)?(?:答案|解析)(?:】|〗)?|^\s*\d{1,2}[.．]\s*解[:：]")

# endregion


# region Models and helpers

@dataclass
class Question:
    year: int
    number: int
    question_type: str
    body: str
    source: Path
    subject: str = "待复核"
    topic: str = "未分类"


def number_from_match(match: re.Match[str]) -> int:
    return int(next(group for group in match.groups() if group is not None))


def clean_body(body: str) -> str:
    answer = ANSWER_RE.search(body)
    if answer:
        body = body[: answer.start()]
    body = re.sub(r"(?m)^#\s+", "", body)
    body = body.strip()
    return body


def question_type_from_heading(heading: str) -> str:
    if "选择" in heading:
        return "选择题"
    if "填空" in heading:
        return "填空题"
    return "解答题"


def select_papers() -> list[tuple[int, Path]]:
    candidates: dict[int, list[Path]] = {}
    for path in PAPERS_DIR.glob("*.md"):
        match = re.match(r"(19|20)\d{2}", path.name)
        if match:
            year = int(path.name[:4])
            candidates.setdefault(year, []).append(path)

    selected: list[tuple[int, Path]] = []
    for year in sorted(candidates):
        override = SOURCE_OVERRIDES.get(year)
        if override:
            selected.append((year, override))
        else:
            selected.append((year, sorted(candidates[year], key=lambda item: len(item.name))[0]))
    return selected


def resolve_image(source: Path, image_name: str) -> Path | None:
    direct = source.parent / "images" / image_name
    paper_scoped = PAPERS_DIR / "images" / source.stem / image_name
    for candidate in (direct, paper_scoped):
        if candidate.is_file():
            return candidate
    matches = list(ROOT.glob(f"**/{image_name}"))
    return matches[0] if len(matches) == 1 else None


def relative_path(path: Path, directory: Path) -> str:
    return os.path.relpath(path, directory).replace("\\", "/")


def relative_image_paths(body: str, source: Path, target_directory: Path) -> str:
    pattern = re.compile(r"!\[[^]]*]\(images/([^\s)]+)\)")

    def replace(match: re.Match[str]) -> str:
        image = resolve_image(source, match.group(1))
        if image is None:
            return match.group(0)
        return f"![](<{relative_path(image, target_directory)}>)"

    return pattern.sub(replace, body)

# endregion


# region Parsing

def parse_early_paper(year: int, source: Path, text: str) -> list[Question]:
    sections = list(SECTION_RE.finditer(text))
    questions: list[Question] = []
    next_number = 1

    for index, section in enumerate(sections):
        heading = section.group(2)
        start = section.end()
        end = sections[index + 1].start() if index + 1 < len(sections) else len(text)
        body = text[start:end].strip()
        count_match = re.search(r"共\s*(\d+)\s*小题", heading)
        expected_count = int(count_match.group(1)) if count_match else 1
        markers = list(NUMBER_RE.finditer(body))
        sequential = markers[:expected_count]
        valid_sequence = (
            expected_count > 1
            and len(sequential) == expected_count
            and [number_from_match(item) for item in sequential] == list(range(1, expected_count + 1))
        )

        if valid_sequence:
            for item_index, marker in enumerate(sequential):
                item_end = sequential[item_index + 1].start() if item_index + 1 < len(sequential) else len(body)
                item_body = clean_body(body[marker.start():item_end])
                questions.append(Question(year, next_number, question_type_from_heading(heading), item_body, source))
                next_number += 1
        elif body:
            questions.append(Question(year, next_number, question_type_from_heading(heading), clean_body(body), source))
            next_number += 1
    return questions


def parse_modern_paper(year: int, source: Path, text: str) -> list[Question]:
    if year == 2021:
        text = re.sub(r"(?m)^\(2\)(?=\s*设函数\s*\$y)", "12）", text)
        text = re.sub(r"(?m)^\(3\)(?=\s*欧拉方程)", "13）", text)
        text = re.sub(r"(?m)^4）(?=\s*设\s*\$\\Sigma)", "14）", text)
        text = re.sub(r"(?m)^5）(?=\s*设\s*\$\\mathbf)", "15）", text)
    if year == 2022:
        text = re.sub(r"(?m)^设数列\s*\$\\\{x_", "3 设数列 $\\{x_", text, count=1)
        text = re.sub(r"(?m)^若\s*\$I_\{1\}", "4 若 $I_{1}", text, count=1)
        text = re.sub(r"(?m)^下列4个条件中", "5 下列4个条件中", text, count=1)

    first_section = SECTION_RE.search(text)
    if not first_section:
        return []

    search_text = text[first_section.start():]
    sections = list(SECTION_RE.finditer(search_text))
    markers = list(NUMBER_RE.finditer(search_text))
    if year == 2024:
        bracket_re = re.compile(r"【\s*(\d{1,2})\s*】")
        markers = list(bracket_re.finditer(search_text))
    questions: list[Question] = []
    accepted: list[re.Match[str]] = []
    expected = 1
    for marker in markers:
        number = number_from_match(marker)
        if number == expected:
            accepted.append(marker)
            expected += 1

    for index, marker in enumerate(accepted):
        number = number_from_match(marker)
        end = accepted[index + 1].start() if index + 1 < len(accepted) else len(search_text)
        body = clean_body(search_text[marker.start():end])
        preceding = [section for section in sections if section.start() < marker.start()]
        heading = preceding[-1].group(2) if preceding else ""
        questions.append(Question(year, number, question_type_from_heading(heading), body, source))
    return questions


def parse_paper(year: int, source: Path) -> list[Question]:
    text = source.read_text(encoding="utf-8").replace("\r\n", "\n")
    if year <= 2003:
        return parse_early_paper(year, source, text)
    return parse_modern_paper(year, source, text)

# endregion


# region Classification

def fallback_subject(year: int, number: int) -> str:
    if year >= 2021:
        if number in {5, 6, 7, 15, 21}:
            return "线性代数"
        if number in {8, 9, 10, 16, 22}:
            return "概率论与数理统计"
        return "高等数学"
    if year >= 2004:
        if number in {5, 6, 13, 20, 21}:
            return "线性代数"
        if number in {7, 8, 14, 22, 23}:
            return "概率论与数理统计"
        return "高等数学"
    return "待复核"


def classify(question: Question) -> None:
    text = re.sub(r"\s+", "", question.body).lower()
    scores: list[tuple[int, str, str]] = []
    for (subject, topic), keywords in TOPICS.items():
        score = sum(2 if keyword.lower().replace(" ", "") in text else 0 for keyword in keywords)
        if score:
            scores.append((score, subject, topic))

    if scores:
        scores.sort(key=lambda item: (item[0], item[1] != "高等数学"), reverse=True)
        _, question.subject, question.topic = scores[0]
        return

    question.subject = fallback_subject(question.year, question.number)
    question.topic = "其他" if question.subject != "待复核" else "未分类"

# endregion


# region Output

def render_question(question: Question, target_directory: Path) -> str:
    body = relative_image_paths(question.body, question.source, target_directory)
    source_link = relative_path(question.source, target_directory)
    title = f"{question.year} 年数学一{question.question_type}第 {question.number} 题"
    return (
        f"# {title}\n\n"
        f"{body}\n\n"
        "## 来源\n\n"
        f"- 年份：{question.year}\n"
        f"- 题号：第 {question.number} 题\n"
        f"- 题型：{question.question_type}\n"
        f"- 原卷：[{question.source.name}](<{source_link}>)\n"
    )


def write_output(questions: list[Question]) -> None:
    resolved = OUTPUT_DIR.resolve()
    if resolved.parent != ROOT.resolve() or resolved.name != "knowledge":
        raise RuntimeError(f"Refusing to replace unexpected output path: {resolved}")
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir()

    for question in questions:
        directory = OUTPUT_DIR / question.subject / question.topic
        directory.mkdir(parents=True, exist_ok=True)
        filename = f"{question.year}-{question.number:02d}-{question.question_type}.md"
        (directory / filename).write_text(render_question(question, directory), encoding="utf-8", newline="\n")

    for subject_dir in sorted(path for path in OUTPUT_DIR.iterdir() if path.is_dir()):
        subject_lines = [f"# {subject_dir.name}", "", "## 知识点", ""]
        for topic_dir in sorted(path for path in subject_dir.iterdir() if path.is_dir()):
            count = len(list(topic_dir.glob("*.md")))
            subject_lines.append(f"- [{topic_dir.name}](<{topic_dir.name}/README.md>)（{count} 题）")

            topic_lines = [f"# {topic_dir.name}", "", f"共 {count} 道题。", "", "## 题目", ""]
            for question_file in sorted(topic_dir.glob("*.md")):
                label = question_file.stem
                topic_lines.append(f"- [{label}](<{question_file.name}>)")
            topic_lines.extend(["", f"- [返回{subject_dir.name}](<../README.md>)", ""])
            (topic_dir / "README.md").write_text("\n".join(topic_lines), encoding="utf-8", newline="\n")

        subject_lines.extend(["", "- [返回总目录](<../README.md>)", ""])
        (subject_dir / "README.md").write_text("\n".join(subject_lines), encoding="utf-8", newline="\n")

    readme_lines = [
        "# 考研数学一按知识点题库",
        "",
        "本目录由历年数学一原卷逐题切分生成。每道题只保留原题内容和来源信息。",
        "",
        f"当前共收录 **{len(questions)}** 道题。",
        "",
        "## 目录",
        "",
    ]
    for subject_dir in sorted(path for path in OUTPUT_DIR.iterdir() if path.is_dir()):
        count = sum(1 for path in subject_dir.rglob("*.md") if path.name != "README.md")
        readme_lines.append(f"- [{subject_dir.name}](<{subject_dir.name}/README.md>)（{count} 题）")
    readme_lines.extend(["", "## 说明", "", "- [查看原始试卷](<../papers/README.md>)", "- 综合题按主要知识点存放一份。", "- `待复核/未分类/` 中的题目需要人工确认知识点。", ""])
    (OUTPUT_DIR / "README.md").write_text("\n".join(readme_lines), encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="replace knowledge/ with generated files")
    args = parser.parse_args()

    all_questions: list[Question] = []
    for year, source in select_papers():
        questions = parse_paper(year, source)
        for question in questions:
            classify(question)
        all_questions.extend(questions)
        print(f"{year}: {len(questions):2d}  {source.name}")

    unclassified = sum(question.subject == "待复核" for question in all_questions)
    print(f"total: {len(all_questions)}")
    print(f"unclassified: {unclassified}")
    if args.write:
        write_output(all_questions)
        print(f"written: {OUTPUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# endregion

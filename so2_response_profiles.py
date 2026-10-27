"""Build and render exact joint-answer profiles for three SO2 matrix questions."""

from collections import Counter, defaultdict
from typing import Any, Callable, Mapping, Sequence


PROFILE_GROUPS = (
    ("legal-barriers", "Legal barriers", tuple(range(63, 67)),
     ("Data protection\\\\(GDPR)", "Licensing\\\\restrictions", "Unclear data\\\\ownership", "Cross-border\\\\restrictions")),
    ("organisational-barriers", "Organisational barriers", tuple(range(68, 72)),
     ("Lack of sharing\\\\agreements", "Bureaucratic\\\\delays", "Missing contact\\\\points / unclear\\\\responsibilities", "Reluctance to\\\\share data")),
    ("collaboration", "Collaboration ratings", tuple(range(73, 77)),
     ("Local", "National", "Europe-wide", "Outside Europe")),
)
PALETTE = {
    "never": ("E7F3F0", "24574E", "Never"),
    "rarely": ("ADCCC3", "173F36", "Rarely"),
    "occasionally": ("4A9281", "FFFFFF", "Occasionally"),
    "frequently": ("155A4B", "FFFFFF", "Frequently"),
    "very poor": ("E7F3F0", "24574E", "Very poor"),
    "poor": ("C8E0D8", "173F36", "Poor"),
    "fair": ("ADCCC3", "173F36", "Fair"),
    "good": ("4A9281", "FFFFFF", "Good"),
    "excellent": ("155A4B", "FFFFFF", "Excellent"),
    "not applicable": ("DFE5EA", "33434C", "Not applicable"),
    "Conflicting answers": ("F2D5A4", "563A12", "Conflict"),
    "Missing": ("ECECEC", "4F4F4F", "Missing"),
}


def build_profile_groups(questions: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Group identical complete answer vectors using canonical observation identities.

    Args:
        questions: Validated SO2 question payloads with source-row contribution
            identities, including explicit Missing and Conflicting answers states.

    Returns:
        Joint models for available approved matrix groups. Every observation
        contributes once per group, with source rows retained per profile. Inputs
        are not mutated, source submissions are not expanded, and percentages use N.

    Raises:
        ValueError: If matrix items, answer counts or observation identities cannot
            be reconciled exactly, or unsupported categories are encountered.
    """
    result = []
    for group_id, title, numbers, headers in PROFILE_GROUPS:
        items = []
        for number in numbers:
            candidates = [q for q in questions if str(q["question_id"]).startswith(f"q_{number:03d}_")]
            if len(candidates) > 1:
                raise ValueError(f"Duplicate matrix item q_{number:03d} in {group_id}")
            items.extend(candidates)
        if not items:
            continue
        if len(items) != 4 or any(q["question_type"] != "single_choice" for q in items):
            raise ValueError(f"Profile group {group_id} requires four single-choice matrix items")
        parents = {q.get("form", {}).get("matrix_parent") for q in items}
        if len(parents) != 1 or None in parents:
            raise ValueError(f"Profile group {group_id} requires one verified matrix parent")
        maps = []
        for question in items:
            values = {}
            for contribution in question["contributions"]:
                row, value = contribution["source_row"], contribution["value"]
                if isinstance(row, bool) or not isinstance(row, int) or row < 1:
                    raise ValueError(f"Invalid observation identity in {group_id}")
                if row in values:
                    raise ValueError(f"Duplicate observation identity {row} in {group_id}")
                if value not in PALETTE:
                    raise ValueError(f"Unsupported profile category {value!r} in {group_id}")
                values[row] = value
            expected = {c["value"]: c["count"] for c in question["categories"]}
            if len(expected) != len(question["categories"]):
                raise ValueError(f"Duplicate category labels in {group_id}")
            observed = Counter(values.values())
            if len(values) != question["population"]["N"] or any(observed[v] != n for v, n in expected.items()) or set(observed) - set(expected):
                raise ValueError(f"Profile counts disagree with question totals in {group_id}")
            population = question["population"]
            if (sum(expected.values()) != population["N"]
                    or observed["Missing"] != population["M"]
                    or len(values)-observed["Missing"] != population["A"]):
                raise ValueError(f"Profile missing/answered totals disagree with N/A/M in {group_id}")
            maps.append(values)
        identities = set(maps[0])
        if any(set(values) != identities for values in maps[1:]):
            raise ValueError(f"Matrix observation identities do not align in {group_id}")
        membership = defaultdict(list)
        for row in sorted(identities):
            membership[tuple(values[row] for values in maps)].append(row)
        ordered_values = (("never", "rarely", "occasionally", "frequently") if group_id != "collaboration"
                          else ("very poor", "poor", "fair", "good", "excellent", "not applicable"))
        ordered_values += ("Conflicting answers", "Missing")
        if any(value not in ordered_values for values in maps for value in values.values()):
            raise ValueError(f"Unsupported answer category for the scale in {group_id}")
        ranks = {value: index for index, value in enumerate(ordered_values)}
        patterns = sorted(membership, key=lambda vector: (-len(membership[vector]), tuple(ranks[v] for v in vector)))
        n = len(identities)
        result.append({"id": group_id, "title": title, "parent_question": next(iter(parents)),
                       "question_ids": [q["question_id"] for q in items],
                       "question_labels": [q["label"] for q in items], "headers": list(headers),
                       "N": n, "ordered_values": list(ordered_values),
                       "profiles": [{"id": f"P{index+1:02d}", "answers": list(vector),
                                     "count": len(membership[vector]), "percent": 100*len(membership[vector])/n,
                                     "source_rows": membership[vector]}
                                    for index, vector in enumerate(patterns)]})
    return result


def profile_fragment(group: Mapping[str, Any], complete: bool, escape: Callable[[str], str]) -> str:
    """Render the approved joint matrix with a shared count scale and bounded size.

    Args:
        group: Reconciled four-item joint model returned by build_profile_groups.
        complete: Whether to show every profile, rather than the first twelve.
        escape: Existing report text-to-TeX escaping function for labels and titles.

    Returns:
        Native TikZ figure, constrained to printable width and 82 percent of text
        height. Category colours encode ranks only; bars encode exact counts.
        Missing/conflict/not-applicable states are not part of the ordinal scale.
    """
    profiles = group["profiles"] if complete else group["profiles"][:12]
    if not profiles:
        return r"\noindent No observations available for joint profiles.\par"
    pitch = min(2.7, 205 / len(profiles)) if complete else 7.2
    fontsize = min(6, pitch * 2.2) if complete else 9
    size = rf"\fontsize{{{fontsize:.2f}}}{{{fontsize+0.5:.2f}}}\selectfont"
    maximum = max(p["count"] for p in group["profiles"])
    coverage = sum(p["count"] for p in profiles)
    n = group["N"]
    title = "All joint-response profiles" if complete else "12 most frequent joint-response profiles"
    out = [r"\begingroup", r"\setbox0=\hbox{", r"\begin{tikzpicture}[x=1mm,y=1mm,text=bbmriBlue]",
           rf"\node[anchor=north west,font=\sffamily\bfseries\large] at (0,20) {{{escape(group['title'])}}};",
           rf"\node[anchor=north west,font=\sffamily\small] at (0,13) {{{title}}};",
           rf"\node[anchor=north west,font=\sffamily\scriptsize] at (0,6) {{Coverage: {coverage}/{n} observations ({100*coverage/n:.1f}\%); {len(profiles)} profiles.}};"]
    for name, x in [("Profile", 3), *zip(group["headers"], (25, 51, 77, 103)), (f"Count (\\% of {n})", 152)]:
        out.append(rf"\node[align=center,font=\sffamily\scriptsize,anchor=north] at ({x},-2) {{{name}}};")
    for i, profile in enumerate(profiles):
        y = -20 - pitch*i
        height = pitch - (0.3 if complete else 1)
        out.append(rf"\node[font=\sffamily{size}] at (3,{y:.2f}) {{{profile['id']}}};")
        for j, answer in enumerate(profile["answers"]):
            fill, foreground, text = PALETTE[answer]
            out.extend([rf"\definecolor{{profileTile}}{{HTML}}{{{fill}}}", rf"\definecolor{{profileText}}{{HTML}}{{{foreground}}}",
                        rf"\fill[profileTile] ({13+26*j},{y-height/2:.2f}) rectangle ({37+26*j},{y+height/2:.2f});",
                        rf"\node[text=profileText,font=\sffamily{size}] at ({25+26*j},{y:.2f}) {{{escape(text)}}};"])
        barheight = min(1.6, pitch*0.6) if complete else 4
        out.extend([rf"\fill[black!5] (120,{y-barheight/2:.2f}) rectangle (140,{y+barheight/2:.2f});",
                    rf"\fill[bbmriBlue] (120,{y-barheight/2:.2f}) rectangle ({120+20*profile['count']/maximum:.2f},{y+barheight/2:.2f});",
                    rf"\node[anchor=west,font=\sffamily{size}] at (143,{y:.2f}) {{{profile['count']} ({profile['percent']:.1f}\%)}};"])
    bottom = -20-pitch*(len(profiles)-1)-pitch/2-5
    scale = "Never to Frequently" if group["id"] != "collaboration" else "Very poor to Excellent"
    out.append(rf"\node[anchor=north west,text width=171mm,font=\sffamily\scriptsize,align=left] at (0,{bottom:.2f}) {{Colour order: {scale}. Conflict, Missing and Not applicable are separate states.\par Shared count scale: maximum {maximum} observations. Each observation belongs to one profile.\par Denominator includes all selected observations, including unresolved submissions and exceptional answers.}};")
    if not complete and coverage < n:
        out.append(rf"\node[anchor=north west,text width=171mm,font=\sffamily\scriptsize] at (0,{bottom-18:.2f}) {{Only {100*coverage/n:.1f}\% of observations are shown; see the complete figure for all responses.}};")
    out.extend([r"\end{tikzpicture}}", r"\ifdim\wd0>\linewidth\setbox0=\hbox{\resizebox{\linewidth}{!}{\box0}}\fi",
                r"\ifdim\dimexpr\ht0+\dp0\relax>0.82\textheight\setbox0=\hbox{\resizebox*{!}{0.82\textheight}{\box0}}\fi",
                r"\noindent\box0\par", r"\endgroup"])
    return "\n".join(out)

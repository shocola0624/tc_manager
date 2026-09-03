from __future__ import annotations

# Discord へ投稿する文言の辞書。表示文字列をコードに直接書かず、必ず translate() を
# 経由させる(CLAUDE.md §7)。現時点では ja のみ提供する。
#
# アナウンス本文・ボタンラベルは全員に見える1通のメッセージのため常に ja 固定で送る。
# 押下者本人にしか見えない follow-up は users.locale -> ja の順で解決する(§7-3 準拠)。
_JA: dict[str, str] = {
    "announce.title": "{title}",
    "announce.body": (
        "## {title}\n"
        "日時: {datetime}\n"
        "場所: {location}\n"
        "\n"
        "下のボタンから出欠を回答してください。"
    ),
    "announce.body.no_location": (
        "## {title}\n"
        "日時: {datetime}\n"
        "\n"
        "下のボタンから出欠を回答してください。"
    ),
    "button.attending": "出席",
    "button.absent": "欠席",
    "button.undecided": "未定",
    "followup.recorded.attending": "「出席」として記録しました。",
    "followup.recorded.absent": "「欠席」として記録しました。",
    "followup.recorded.undecided": "「未定」として記録しました。",
    "followup.registration_required": (
        "回答するには先にWebアプリでログイン・登録を完了してください。\n{url}"
    ),
    "followup.error": "エラーが発生しました。しばらくしてから再度お試しください。",
    "notify.absent_with_assignment": (
        "「{activity_title}」を欠席にしましたが、持参担当のままの持ち物があります: {items}。\n"
        "担当を外すか、他の方に引き継いでください。"
    ),
    "notify.item_needed_while_absent": (
        "「{activity_title}」であなたの持ち物「{item_name}」が必要とされています(担当: {assignee_name})。\n"
        "参加されない場合は、事前に該当の方へお渡しください。"
    ),
    # 活動確定アナウンス(discord_bot/confirm_announce.py)のカテゴリー見出し用。
    # frontend/src/i18n/locales/ja.json の categories と同じ訳語を使う。
    "category.dripper": "ドリッパー",
    "category.grinder": "グラインダー",
    "category.scale": "スケール",
    "category.kettle": "ケトル",
    "category.pot": "ポット",
    "category.scoop": "スクープ",
    "category.thermometer": "温度計",
    "category.server": "サーバー",
    "category.other": "その他",
}

_LOCALES: dict[str, dict[str, str]] = {"ja": _JA}


def translate(locale: str | None, key: str, **params: str) -> str:
    dict_ = _LOCALES.get(locale or "ja", _JA)
    template = dict_.get(key, _JA.get(key, key))
    return template.format(**params)

// Discord REST API のみを使う薄いクライアント(backend/auth/discord_client.py の
// DiscordBotClient と同じ方針)。Gateway(WebSocket)は使わない。

const DISCORD_API_BASE = "https://discord.com/api/v10";

export class DiscordApiError extends Error {}

/** 指定チャンネルへメッセージを送信する。 */
export async function postChannelMessage(botToken: string, channelId: string, content: string): Promise<void> {
  const response = await fetch(`${DISCORD_API_BASE}/channels/${channelId}/messages`, {
    method: "POST",
    headers: { Authorization: `Bot ${botToken}`, "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
  if (!response.ok) {
    throw new DiscordApiError(`create message failed: ${response.status} ${await response.text()}`);
  }
}

/** 指定ユーザーとのDMチャンネルを開いてメッセージを送信する。
 * 相手がBotと同じギルドにいない、DMを拒否している等で失敗しうる
 * (呼び出し元で1件ずつ例外を捕捉し、他の送信を止めない設計にする)。 */
export async function sendDirectMessage(botToken: string, discordUserId: string, content: string): Promise<void> {
  const openResponse = await fetch(`${DISCORD_API_BASE}/users/@me/channels`, {
    method: "POST",
    headers: { Authorization: `Bot ${botToken}`, "Content-Type": "application/json" },
    body: JSON.stringify({ recipient_id: discordUserId }),
  });
  if (!openResponse.ok) {
    throw new DiscordApiError(`open DM channel failed: ${openResponse.status} ${await openResponse.text()}`);
  }
  const { id: channelId } = (await openResponse.json()) as { id: string };
  await postChannelMessage(botToken, channelId, content);
}

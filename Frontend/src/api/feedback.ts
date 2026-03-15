import { apiFetch } from './auth';

export async function setMessageLike(
  messageId: string,
  isLiked: boolean | null,
  description?: string,
): Promise<void> {
  const res = await apiFetch(`/messages/${messageId}/like`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      is_liked: isLiked,
      description: description?.trim() || null,
    }),
  });
  if (!res.ok) throw new Error('Failed to submit feedback');
}

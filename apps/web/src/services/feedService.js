import { apiAssetUrl, apiRequest, apiUrl } from '../api/client'

const headers = () => ({ Authorization: `Bearer ${localStorage.getItem('libria_token')}` })
export const feedService = {
  summary: (audience, signal) => apiRequest(`/mural?audience=${audience}`, { headers: headers(), signal }),
  page: (audience, category, cursor, signal) => apiRequest(`/mural/${category}?${new URLSearchParams({ audience, ...(cursor ? { cursor } : {}) })}`, { headers: headers(), signal }),
}

// Adapter for the existing full publication and its unchanged interaction endpoints.
export function toFeedPost(item) {
  return {
    activity: item,
    eventDetails: item.event_details || null,
    id: item.id, type: item.kind, feedItemType: item.feed_item_type, authorProfileId: item.author_profile_id,
    images: item.images || [], likeCount: item.like_count || 0, likedByMe: item.liked_by_me || false,
    followingAuthor: item.following_author || false, author: item.author, authorRole: item.author_role, avatarUrl: item.avatar_url ? apiAssetUrl(item.avatar_url) : null,
    initials: item.author.split(' ').slice(0, 2).map(part => part[0]).join('').toUpperCase(),
    time: new Date(item.created_at).toLocaleString('es-CL'), title: item.title, text: item.body,
    source: item.source, publicationType: item.publication_type, bookId: item.book_ref || item.work_id,
    bookTitle: item.book_title, bookAuthor: item.book_author, rating: item.rating,
    progressPercent: item.progress_percent, bookCoverUrl: item.book_cover_url ? apiAssetUrl(item.book_cover_url) : null,
    customBookCoverUrl: item.custom_book_cover_url ? apiUrl(item.custom_book_cover_url) : null, canEditBookCover: item.can_edit_book_cover || false,
    readingEvent: item.reading_event, isSpoiler: item.is_spoiler || false, color: 'var(--secondary)',
  }
}

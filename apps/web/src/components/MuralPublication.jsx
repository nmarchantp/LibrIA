import FeedCard from './FeedCard'
import { useActivityInteractions } from '../context/ActivityInteractionContext'
import { toFeedPost } from '../services/feedService'

// Reuse the original full publication and its gallery/comments, with shared counts.
export default function MuralPublication({ item }) {
  const interactions = useActivityInteractions(item)
  return <FeedCard post={toFeedPost(item)} interactions={interactions} widePublication />
}

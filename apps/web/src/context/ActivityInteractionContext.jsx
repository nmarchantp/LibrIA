import { createContext, useContext, useEffect, useMemo, useSyncExternalStore } from 'react'
import { createInteractionStore } from '../services/activityInteractions'

const Context = createContext(null)

export function ActivityInteractionProvider({ children }) {
  const store = useMemo(createInteractionStore, [])
  return <Context.Provider value={store}>{children}</Context.Provider>
}

// The hooks and provider deliberately share this small, mural-only context.
// eslint-disable-next-line react-refresh/only-export-components
export function useActivityStore() {
  const store = useContext(Context)
  if (!store) throw new Error('Se requiere ActivityInteractionProvider')
  return store
}

// eslint-disable-next-line react-refresh/only-export-components
export function useActivityInteractions(item) {
  const store = useActivityStore()
  const value = useSyncExternalStore(store.subscribe, () => store.get(item))
  useEffect(() => { store.seed(item) }, [store, item])
  return { ...value, toggleLike: () => store.toggleLike(item), view: action => store.view(item, action),
    loadComments: signal => store.comments(item, signal), addComment: body => store.comment(item, body), updateComment:(id,body)=>store.updateComment(item,id,body),deleteComment:id=>store.deleteComment(item,id) }
}

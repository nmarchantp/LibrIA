import { createContext, useContext } from 'react'

export const AuthJourneyContext = createContext({ holding: false, motionEnabled: true, setMotionEnabled: () => {}, run: async (_scene, operation, navigate) => { if (await operation?.() !== false) navigate() } })
export const useAuthJourney = () => useContext(AuthJourneyContext)

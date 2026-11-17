import AdaptiveAnalysis from '../components/AdaptiveAnalysis'

export default function InsightsPage({ active = true, children }) { return <AdaptiveAnalysis scope="profile" active={active}>{children}</AdaptiveAnalysis> }

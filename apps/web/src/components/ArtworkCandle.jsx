import CandleFlameShape from './CandleFlameShape'

// Exposed flames, including the desert oil lamp. Enclosed lanterns keep their glow.
export const artworkCandles = {
  'arenas-destino':[[65,69.2,3.5,18]],
  'olimpo-eterno':[[66.7,106.7,3.2,16]],
  'dark-dorado':[[20,93,2.2,11]],
  'oraculo-luna':[[23.1,72.6,1.7,8],[13.4,97.9,1.5,8],[19.1,114.6,1.5,7]],
  'catedral-cristal':[[22.5,59,1.7,8],[12.7,67.1,1.4,6],[32.5,68.8,1.4,6]],
  'ecos-sombras':[[32.3,51.3,2,9],[24.3,64,1.5,7],[82.2,103.8,2,11]],
  'aquelarre-medianoche':[[71.5,77,2.1,9.5],[87,93,1.9,9]],
}

export default function ArtworkCandle({ candle, id, index }) {
  const [x,y,,height]=candle
  return <g className="artwork-candle" transform={`translate(${x} ${y}) scale(${height/179}) translate(-890 -210)`} style={{'--candle-delay':`${-index*.17}s`}}>
    <rect className="artwork-candle-hit" x="790" y="0" width="200" height="255" fill="transparent" />
    <ellipse className="artwork-candle-halo" cx="890" cy="135" rx="220" ry="260" fill={`url(#${id}-candle-halo)`} />
    <CandleFlameShape className="sidebar-candle-flame-shape artwork-candle-flame" fireId={`${id}-candle-fire`} glowId={`${id}-candle-local-glow`} />
  </g>
}

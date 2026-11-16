import './ArtworkLamp.css'

// Lamp-specific presets. Coordinates share the sidebar's 100 x 150 canvas.
export const artworkLamps = {
  'archivo-galactico':{x:50.5,y:29,length:72,topWidth:16,bottomWidth:62,offset:-5,color:'#8cecff'},
}

export default function ArtworkLamp({ lamp, id }) {
  const {x,y,length,topWidth,bottomWidth,offset=0,color}=lamp
  const bottomX=x+offset, bottomY=y+length
  const beam=`M${x-topWidth/2} ${y} Q${x} ${y+2} ${x+topWidth/2} ${y} L${bottomX+bottomWidth/2} ${bottomY} Q${bottomX} ${bottomY+6} ${bottomX-bottomWidth/2} ${bottomY}Z`
  return <g className="artwork-lamp">
    <defs>
      <linearGradient id={`${id}-lamp-beam`} x1="0" y1="0" x2="0" y2="1">
        <stop stopColor={color} stopOpacity=".85" /><stop offset=".55" stopColor={color} stopOpacity=".32" /><stop offset=".82" stopColor={color} stopOpacity=".16" /><stop offset="1" stopColor={color} stopOpacity="0" />
      </linearGradient>
      <radialGradient id={`${id}-lamp-source`}><stop stopColor="#f2fdff" /><stop offset=".3" stopColor={color} stopOpacity=".9" /><stop offset="1" stopColor={color} stopOpacity="0" /></radialGradient>
    </defs>
    <g className="artwork-lamp-illumination">
      <path className="artwork-lamp-beam" d={beam} fill={`url(#${id}-lamp-beam)`} />
      <ellipse cx={x} cy={y} rx={topWidth*.7} ry="3.2" fill={`url(#${id}-lamp-source)`} />
      <ellipse cx={bottomX} cy={bottomY-1} rx={bottomWidth*.45} ry="7" fill={`url(#${id}-lamp-source)`} opacity=".4" />
    </g>
    <path className="artwork-lamp-hit" d={beam} fill="transparent" />
    <ellipse className="artwork-lamp-hit" cx={x} cy={y-2} rx={topWidth*.8} ry="7" fill="transparent" />
  </g>
}

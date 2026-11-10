import { useId,useLayoutEffect,useRef,useState } from 'react'
import { apiUrl } from '../api/client'
import { EventDate,EventInformation } from './EventPresentation'
import FormattedText from './FormattedText'
import PostGallery from './PostGallery'


export default function MuralEventContent({post,onOpen}){
  const root=useRef(null),measure=useRef(null)
  const [expanded,setExpanded]=useState(false),[layout,setLayout]=useState({overflow:false,lines:0,lineHeight:0})
  const contentId=useId()
  useLayoutEffect(()=>{
    const text=measure.current.querySelector('.post-text')
    let active=true
    const update=()=>{
      if(!active)return
      const lineHeight=parseFloat(getComputedStyle(text).lineHeight)
      if(!lineHeight)return
      const full=text.getBoundingClientRect().height
      const lines=parseInt(getComputedStyle(root.current).getPropertyValue('--event-description-lines'),10)||6
      const overflow=full>lines*lineHeight+1
      setLayout(previous=>previous.overflow===overflow&&previous.lines===lines&&previous.lineHeight===lineHeight?previous:{overflow,lines,lineHeight})
    }
    const observer=new ResizeObserver(update)
    observer.observe(text)
    update();document.fonts?.ready.then(update)
    return()=>{active=false;observer.disconnect()}
  },[post.text,post.title,post.eventDetails])
  const collapsed=layout.overflow&&!expanded
  return <div ref={root} className="mural-event-content">
    <EventDate details={post.eventDetails} />
    <div className="mural-event-message"><div className="mural-event-heading"><h2>{post.title}</h2><div className="mural-event-heading-metadata"><EventInformation details={post.eventDetails} /></div></div>
      <div className="mural-event-description">
        <div ref={measure} className="mural-event-description-measure" aria-hidden="true" inert><FormattedText className="post-text" text={post.text} /></div>
        <div id={contentId} className={collapsed?'mural-event-description-text is-collapsed':'mural-event-description-text'} style={collapsed?{'--event-description-lines':Math.max(1,layout.lines),'--event-description-height':`${layout.lines*layout.lineHeight}px`}:undefined}><FormattedText className="post-text" text={post.text} /></div>
        {layout.overflow&&<button type="button" className="mural-event-description-toggle" aria-expanded={expanded} aria-controls={contentId} onClick={()=>setExpanded(value=>!value)}>{expanded?'Ver menos':'Ver más'}</button>}
      </div>
      <PostGallery images={post.images.map(value=>/^https?:\/\//i.test(value)?value:apiUrl(value))} alt={`Fotografía del evento ${post.title}`} onOpen={onOpen} editorial />
    </div>
  </div>
}

import './MagicalBackground.css'

// Mounted once by Layout; route changes do not restart these CSS animations.
export default function MagicalBackground() {
  return <div className="profile-starfield" aria-hidden="true">
    <span className="profile-starfield-layer profile-starfield-layer--fine" />
    <span className="profile-starfield-layer profile-starfield-layer--medium" />
    <span className="profile-starfield-layer profile-starfield-layer--large" />
  </div>
}

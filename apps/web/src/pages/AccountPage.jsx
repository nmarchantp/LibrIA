import GoogleAccountPanel from '../components/GoogleAccountPanel'
import AccountManagement from '../components/AccountManagement'
import './AccountPage.css'

export default function AccountPage() {
  return <div className="account-page">
    <AccountManagement />
    <GoogleAccountPanel />
  </div>
}

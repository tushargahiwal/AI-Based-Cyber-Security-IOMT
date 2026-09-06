const base = {
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.75,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
  viewBox: '0 0 24 24',
}

export const UserIcon = (props) => (
  <svg {...base} {...props}>
    <circle cx="12" cy="8" r="3.5" />
    <path d="M4.5 20c1.4-3.6 4.4-5.5 7.5-5.5s6.1 1.9 7.5 5.5" />
  </svg>
)

export const MailIcon = (props) => (
  <svg {...base} {...props}>
    <rect x="3.5" y="5.5" width="17" height="13" rx="2" />
    <path d="m4 7 8 6 8-6" />
  </svg>
)

export const LockIcon = (props) => (
  <svg {...base} {...props}>
    <rect x="5" y="10.5" width="14" height="9" rx="2" />
    <path d="M8 10.5V8a4 4 0 0 1 8 0v2.5" />
  </svg>
)

export const BuildingIcon = (props) => (
  <svg {...base} {...props}>
    <rect x="4" y="3.5" width="10" height="17" rx="1" />
    <path d="M14 8h6v12.5" />
    <path d="M7.5 7h3M7.5 10.5h3M7.5 14h3M17 11.5h.01M17 15h.01" />
  </svg>
)

export const ShieldIcon = (props) => (
  <svg {...base} {...props}>
    <path d="M12 3.5 5 6v5.5c0 4.5 3 7.7 7 9 4-1.3 7-4.5 7-9V6l-7-2.5Z" />
  </svg>
)

export const EyeIcon = (props) => (
  <svg {...base} {...props}>
    <path d="M2.5 12S5.7 5.5 12 5.5 21.5 12 21.5 12 18.3 18.5 12 18.5 2.5 12 2.5 12Z" />
    <circle cx="12" cy="12" r="3" />
  </svg>
)

export const EyeOffIcon = (props) => (
  <svg {...base} {...props}>
    <path d="M3 3l18 18" />
    <path d="M10.6 5.6A10.7 10.7 0 0 1 12 5.5c6.3 0 9.5 6.5 9.5 6.5a13.4 13.4 0 0 1-3.1 3.9M6.3 7.4A13.6 13.6 0 0 0 2.5 12S5.7 18.5 12 18.5a9.6 9.6 0 0 0 3.3-.6" />
    <path d="M9.9 10a3 3 0 0 0 4.1 4.1" />
  </svg>
)

export const ChevronDownIcon = (props) => (
  <svg {...base} {...props}>
    <path d="m6 9 6 6 6-6" />
  </svg>
)

export const PhoneIcon = (props) => (
  <svg {...base} {...props}>
    <path d="M5 4.5h3.2l1.3 4.2-2 1.6a12.5 12.5 0 0 0 6.2 6.2l1.6-2 4.2 1.3V19a1.5 1.5 0 0 1-1.6 1.5C10.9 19.9 4.1 13.1 3.5 6.1A1.5 1.5 0 0 1 5 4.5Z" />
  </svg>
)

export const MapPinIcon = (props) => (
  <svg {...base} {...props}>
    <path d="M12 21s7-6.5 7-11.5a7 7 0 1 0-14 0C5 14.5 12 21 12 21Z" />
    <circle cx="12" cy="9.5" r="2.5" />
  </svg>
)

export const ChevronRightIcon = (props) => (
  <svg {...base} {...props}>
    <path d="m9 6 6 6-6 6" />
  </svg>
)

export const TrashIcon = (props) => (
  <svg {...base} {...props}>
    <path d="M4.5 7h15" />
    <path d="M9.5 7V5a1.5 1.5 0 0 1 1.5-1.5h2A1.5 1.5 0 0 1 14.5 5v2" />
    <path d="M6.5 7 7.3 19a1.5 1.5 0 0 0 1.5 1.4h6.4a1.5 1.5 0 0 0 1.5-1.4L17.5 7" />
    <path d="M10.2 11v5.5M13.8 11v5.5" />
  </svg>
)

export const PlusIcon = (props) => (
  <svg {...base} {...props}>
    <path d="M12 5v14M5 12h14" />
  </svg>
)

export const LogoutIcon = (props) => (
  <svg {...base} {...props}>
    <path d="M9 4.5H6a1.5 1.5 0 0 0-1.5 1.5v12A1.5 1.5 0 0 0 6 19.5h3" />
    <path d="M14.5 15.5 19 11l-4.5-4.5" />
    <path d="M19 11H9" />
  </svg>
)

export const MonitorIcon = (props) => (
  <svg {...base} {...props}>
    <rect x="3" y="4.5" width="18" height="12" rx="1.5" />
    <path d="M8 20h8M12 16.5V20" />
    <path d="M6.5 8.5 9 12l2-2.5 2 3 2.5-4" />
  </svg>
)

export const TagIcon = (props) => (
  <svg {...base} {...props}>
    <path d="M11 4.5H6A1.5 1.5 0 0 0 4.5 6v5l8.9 8.9a1.5 1.5 0 0 0 2.1 0l4.4-4.4a1.5 1.5 0 0 0 0-2.1L11 4.5Z" />
    <circle cx="8.5" cy="8.5" r="1.25" />
  </svg>
)

export const FirmwareIcon = (props) => (
  <svg {...base} {...props}>
    <rect x="6" y="6" width="12" height="12" rx="1.5" />
    <path d="M9.5 6V3.5M14.5 6V3.5M9.5 20.5V18M14.5 20.5V18M6 9.5H3.5M6 14.5H3.5M20.5 9.5H18M20.5 14.5H18" />
  </svg>
)

export const HeartPulseIcon = (props) => (
  <svg {...base} {...props}>
    <path d="M20.5 8.7c0-2.3-1.9-4.2-4.2-4.2-1.6 0-3 .9-3.8 2.2-.8-1.3-2.2-2.2-3.8-2.2-2.3 0-4.2 1.9-4.2 4.2 0 .7.1 1.3.4 1.9H3.5l2.5 0 1.5-2.5 2 5 2-3.5 1.3 2.1H20a4.6 4.6 0 0 0 .5-1.9Z" />
    <path d="M12.5 19.5c-3-1.9-8-5.4-8-9.6" />
    <path d="M20 9.9c0 4.2-5 7.7-8 9.6" />
  </svg>
)

export const LinkIcon = (props) => (
  <svg {...base} {...props}>
    <path d="M9.5 14.5 14.5 9.5" />
    <path d="M11 6.5 12.6 4.9a3.5 3.5 0 0 1 5 5L16 11.4" />
    <path d="M13 17.5 11.4 19.1a3.5 3.5 0 0 1-5-5L8 12.6" />
  </svg>
)

export const GearIcon = (props) => (
  <svg {...base} {...props}>
    <circle cx="12" cy="12" r="3" />
    <path d="M12 4.5v2M12 17.5v2M19.5 12h-2M6.5 12h-2M17.4 6.6l-1.4 1.4M8 16l-1.4 1.4M17.4 17.4 16 16M8 8 6.6 6.6" />
  </svg>
)

export const BanIcon = (props) => (
  <svg {...base} {...props}>
    <circle cx="12" cy="12" r="8.5" />
    <path d="m6.5 6.5 11 11" />
  </svg>
)

export const DatabaseIcon = (props) => (
  <svg {...base} {...props}>
    <ellipse cx="12" cy="6" rx="7.5" ry="3" />
    <path d="M4.5 6v6c0 1.7 3.4 3 7.5 3s7.5-1.3 7.5-3V6" />
    <path d="M4.5 12v6c0 1.7 3.4 3 7.5 3s7.5-1.3 7.5-3v-6" />
  </svg>
)

export const AlertTriangleIcon = (props) => (
  <svg {...base} {...props}>
    <path d="M12 4 3 20h18L12 4Z" />
    <path d="M12 10v4M12 17h.01" />
  </svg>
)

export const NetworkIcon = (props) => (
  <svg {...base} {...props}>
    <circle cx="12" cy="5" r="2" />
    <circle cx="5" cy="19" r="2" />
    <circle cx="19" cy="19" r="2" />
    <path d="M12 7v4M12 11 6.3 17.3M12 11l5.7 6.3" />
  </svg>
)

export const SlidersIcon = (props) => (
  <svg {...base} {...props}>
    <path d="M5 6h14M5 12h14M5 18h14" />
    <circle cx="9" cy="6" r="1.75" fill="currentColor" />
    <circle cx="16" cy="12" r="1.75" fill="currentColor" />
    <circle cx="10" cy="18" r="1.75" fill="currentColor" />
  </svg>
)

export const KeyIcon = (props) => (
  <svg {...base} {...props}>
    <circle cx="8" cy="15" r="3.5" />
    <path d="M10.5 12.5 18 5M15.5 8l2 2M18 5.5l2 2" />
  </svg>
)

export const HistoryIcon = (props) => (
  <svg {...base} {...props}>
    <path d="M4 12a8 8 0 1 0 2.5-5.8" />
    <path d="M4 4.5V9h4.5" />
    <path d="M12 8v4l3 2" />
  </svg>
)

export const CpuIcon = (props) => (
  <svg {...base} {...props}>
    <rect x="7" y="7" width="10" height="10" rx="1.5" />
    <rect x="10" y="2.5" width="4" height="3" />
    <rect x="10" y="18.5" width="4" height="3" />
    <rect x="2.5" y="10" width="3" height="4" />
    <rect x="18.5" y="10" width="3" height="4" />
  </svg>
)

export const CheckCircleIcon = (props) => (
  <svg {...base} {...props}>
    <circle cx="12" cy="12" r="8.5" />
    <path d="m8.5 12.3 2.4 2.4 4.6-5" />
  </svg>
)

export const ActivityIcon = (props) => (
  <svg {...base} {...props}>
    <path d="M3 12h4l2.5-7 4 14 2.5-7H21" />
  </svg>
)

export const BellIcon = (props) => (
  <svg {...base} {...props}>
    <path d="M6 10.5a6 6 0 1 1 12 0c0 4 1.5 5.5 1.5 5.5h-15S6 14.5 6 10.5Z" />
    <path d="M10 19.5a2 2 0 0 0 4 0" />
  </svg>
)

export const MessageIcon = (props) => (
  <svg {...base} {...props}>
    <path d="M4 5.5h16v11H8l-4 3.5v-3.5H4Z" />
  </svg>
)

export const UserCheckIcon = (props) => (
  <svg {...base} {...props}>
    <circle cx="9" cy="8" r="3.5" />
    <path d="M3 19c1.2-3.2 3.7-4.8 6-4.8s4.8 1.6 6 4.8" />
    <path d="m15.5 9.5 2 2 3.5-3.5" />
  </svg>
)

export const SpinnerIcon = (props) => (
  <svg viewBox="0 0 24 24" fill="none" {...props}>
    <circle cx="12" cy="12" r="9" stroke="currentColor" strokeWidth="2.5" opacity="0.2" />
    <path d="M21 12a9 9 0 0 0-9-9" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" />
  </svg>
)

export const GridIcon = (props) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" {...props}>
    <rect x="3" y="3" width="7" height="7" rx="1.5" />
    <rect x="14" y="3" width="7" height="7" rx="1.5" />
    <rect x="3" y="14" width="7" height="7" rx="1.5" />
    <rect x="14" y="14" width="7" height="7" rx="1.5" />
  </svg>
)

export const FileTextIcon = (props) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" {...props}>
    <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
    <path d="M14 3v5h5" />
    <path d="M9 13h6M9 17h4" strokeLinecap="round" />
  </svg>
)

export const FlaskIcon = (props) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" {...props}>
    <path d="M10 3v6.5L4.8 18a2 2 0 0 0 1.7 3h11a2 2 0 0 0 1.7-3L14 9.5V3" />
    <path d="M9 3h6M7.5 14h9" strokeLinecap="round" />
  </svg>
)

export const RadarIcon = (props) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" {...props}>
    <circle cx="12" cy="12" r="9" />
    <circle cx="12" cy="12" r="4.5" />
    <path d="M12 12 19 7" strokeLinecap="round" />
  </svg>
)

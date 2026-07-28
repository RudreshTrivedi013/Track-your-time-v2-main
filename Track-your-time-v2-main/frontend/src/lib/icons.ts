/**
 * The app's entire icon vocabulary — import icons from HERE, never from
 * 'lucide-react' directly.
 *
 * The codebase previously pulled 56 distinct icons across 23 files, including
 * several near-synonyms used interchangeably (Check/CheckCircle/CheckCircle2,
 * Clock/Clock3/TimerReset, Pencil/PenLine/Edit2, Trash/Trash2,
 * MessageCircle/MessageSquare). Funnelling everything through one module keeps
 * the set from drifting back out and keeps the UI visually quiet.
 *
 * Adding one? Ask whether an existing icon already carries that meaning.
 *
 * Current count: 17.
 */
export {
  // Navigation (3)
  Home,
  FileText,
  Settings,

  // Actions (9)
  Plus,
  Check,
  Clock,
  // Vertical, not horizontal: the task row is a single line, so a column of
  // dots takes far less horizontal space and leaves more room for the title.
  MoreVertical,
  Pencil,
  Trash2,
  BellOff,
  RotateCcw,
  Mic,

  // Chrome (5)
  X,
  ChevronDown,
  Loader2,
  LogOut,
  Bell,
} from 'lucide-react'

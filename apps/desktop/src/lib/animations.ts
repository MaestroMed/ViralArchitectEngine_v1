/**
 * Framer Motion animation variants and configs
 * Spring physics for buttery smooth interactions
 */

import type { Variants, Transition } from 'framer-motion';

// Spring physics config - snappy but natural
export const springConfig: Transition = {
  type: 'spring',
  stiffness: 400,
  damping: 30,
};

// Softer spring for larger elements
export const softSpring: Transition = {
  type: 'spring',
  stiffness: 250,
  damping: 25,
};

// Quick spring for micro-interactions
export const quickSpring: Transition = {
  type: 'spring',
  stiffness: 500,
  damping: 35,
};

// Hover & tap animation props
export const hoverScale = {
  whileHover: { scale: 1.02 },
  whileTap: { scale: 0.98 },
  transition: springConfig,
};

// Subtle hover lift
export const hoverLift = {
  whileHover: { y: -2 },
  whileTap: { y: 0 },
  transition: springConfig,
};

// Button press effect
export const buttonPress = {
  whileHover: { scale: 1.02 },
  whileTap: { scale: 0.95 },
  transition: quickSpring,
};

// Card hover effect
export const cardHover = {
  whileHover: { 
    scale: 1.01,
    y: -2,
    boxShadow: '0 10px 30px rgba(0,0,0,0.15)',
  },
  transition: softSpring,
};

// Stagger container for list animations
export const staggerContainer: Variants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: {
      staggerChildren: 0.05,
      delayChildren: 0.1,
    },
  },
};

// Stagger item - fade up
export const staggerItem: Variants = {
  hidden: { opacity: 0, y: 20 },
  show: { 
    opacity: 1, 
    y: 0,
    transition: softSpring,
  },
};

// Slide in from right
export const slideInRight: Variants = {
  hidden: { opacity: 0, x: 50 },
  show: { 
    opacity: 1, 
    x: 0,
    transition: springConfig,
  },
  exit: { 
    opacity: 0, 
    x: -50,
    transition: { duration: 0.2 },
  },
};

// Slide in from bottom
export const slideInBottom: Variants = {
  hidden: { opacity: 0, y: 20 },
  show: { 
    opacity: 1, 
    y: 0,
    transition: springConfig,
  },
  exit: { 
    opacity: 0, 
    y: 20,
    transition: { duration: 0.15 },
  },
};

// Scale fade - for modals
export const scaleFade: Variants = {
  hidden: { 
    opacity: 0, 
    scale: 0.95,
  },
  show: { 
    opacity: 1, 
    scale: 1,
    transition: springConfig,
  },
  exit: { 
    opacity: 0, 
    scale: 0.95,
    transition: { duration: 0.15 },
  },
};

// Fade only
export const fadeOnly: Variants = {
  hidden: { opacity: 0 },
  show: { 
    opacity: 1,
    transition: { duration: 0.2 },
  },
  exit: { 
    opacity: 0,
    transition: { duration: 0.15 },
  },
};

// Page transition variants
export const pageTransition: Variants = {
  initial: { opacity: 0, x: 20 },
  animate: { 
    opacity: 1, 
    x: 0,
    transition: springConfig,
  },
  exit: { 
    opacity: 0, 
    x: -20,
    transition: { duration: 0.15 },
  },
};

// Drawer animation (bottom)
export const drawerVariants: Variants = {
  hidden: { y: '100%' },
  show: { 
    y: 0,
    transition: springConfig,
  },
  exit: { 
    y: '100%',
    transition: { duration: 0.2 },
  },
};

// Backdrop fade
export const backdropVariants: Variants = {
  hidden: { opacity: 0 },
  show: { opacity: 1 },
  exit: { opacity: 0 },
};

// Pulse glow animation for active states
export const pulseGlow: Variants = {
  animate: {
    boxShadow: [
      '0 0 0 0 rgba(16, 185, 129, 0.4)',
      '0 0 0 10px rgba(16, 185, 129, 0)',
      '0 0 0 0 rgba(16, 185, 129, 0)',
    ],
    transition: {
      duration: 2,
      repeat: Infinity,
      ease: 'easeOut',
    },
  },
};

// Number counter animation helper
export const counterSpring: Transition = {
  type: 'spring',
  stiffness: 100,
  damping: 15,
};

// Skeleton loading pulse
export const skeletonPulse: Variants = {
  animate: {
    opacity: [0.5, 1, 0.5],
    transition: {
      duration: 1.5,
      repeat: Infinity,
      ease: 'easeInOut',
    },
  },
};





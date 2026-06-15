/**
 * Onboarding Page
 * 
 * Interactive guide for first-time users
 */

import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Upload,
  Wand2,
  Scissors,
  Download,
  ChevronRight,
  ChevronLeft,
  Check,
  Sparkles,
  ArrowRight,
} from 'lucide-react';

interface OnboardingStep {
  id: string;
  title: string;
  description: string;
  icon: any;
  color: string;
  features: string[];
}

const ONBOARDING_STEPS: OnboardingStep[] = [
  {
    id: 'welcome',
    title: 'Bienvenue sur Forge Lab',
    description: 'L\'outil ultime pour créer des clips viraux à partir de vos streams.',
    icon: Sparkles,
    color: 'from-cyan-500 to-blue-500',
    features: [
      'Détection automatique des meilleurs moments',
      'Sous-titres karaoké style TikTok',
      'Export optimisé pour les réseaux sociaux',
    ],
  },
  {
    id: 'import',
    title: 'Importez votre vidéo',
    description: 'Glissez-déposez une vidéo ou collez un lien YouTube/Twitch.',
    icon: Upload,
    color: 'from-purple-500 to-pink-500',
    features: [
      'Support MP4, MOV, MKV, WebM',
      'Import direct depuis YouTube et Twitch',
      'Extraction automatique de l\'audio',
    ],
  },
  {
    id: 'analyze',
    title: 'Analyse intelligente',
    description: 'L\'IA analyse votre contenu et identifie les moments viraux.',
    icon: Wand2,
    color: 'from-amber-500 to-orange-500',
    features: [
      'Transcription automatique avec Whisper',
      'Détection des émotions et réactions',
      'Score de viralité pour chaque segment',
    ],
  },
  {
    id: 'edit',
    title: 'Éditez comme un pro',
    description: 'Personnalisez votre clip avec notre éditeur 9:16.',
    icon: Scissors,
    color: 'from-green-500 to-emerald-500',
    features: [
      'Layout dynamique facecam + gameplay',
      'Sous-titres personnalisables',
      'Jump cuts automatiques',
    ],
  },
  {
    id: 'export',
    title: 'Exportez et partagez',
    description: 'Rendez votre clip et publiez-le directement.',
    icon: Download,
    color: 'from-blue-500 to-indigo-500',
    features: [
      'Export 1080x1920 optimisé',
      'Encodage GPU ultra-rapide',
      'Publication directe sur TikTok/YouTube',
    ],
  },
];

export default function OnboardingPage() {
  const navigate = useNavigate();
  const [currentStep, setCurrentStep] = useState(0);
  const [completedSteps, setCompletedSteps] = useState<Set<string>>(new Set());

  const step = ONBOARDING_STEPS[currentStep];
  const isLastStep = currentStep === ONBOARDING_STEPS.length - 1;
  const isFirstStep = currentStep === 0;

  const handleNext = () => {
    setCompletedSteps(prev => new Set(prev).add(step.id));
    if (isLastStep) {
      // Mark onboarding as complete and go to home
      localStorage.setItem('forge_onboarding_complete', 'true');
      navigate('/');
    } else {
      setCurrentStep(prev => prev + 1);
    }
  };

  const handlePrev = () => {
    if (!isFirstStep) {
      setCurrentStep(prev => prev - 1);
    }
  };

  const handleSkip = () => {
    localStorage.setItem('forge_onboarding_complete', 'true');
    navigate('/');
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-gray-900 to-gray-800 flex flex-col">
      {/* Progress bar */}
      <div className="fixed top-0 left-0 right-0 h-1 bg-gray-800 z-50">
        <motion.div
          className="h-full bg-gradient-to-r from-cyan-500 to-blue-500"
          initial={{ width: 0 }}
          animate={{ width: `${((currentStep + 1) / ONBOARDING_STEPS.length) * 100}%` }}
          transition={{ duration: 0.3 }}
        />
      </div>

      {/* Skip button */}
      <div className="absolute top-6 right-6">
        <button
          onClick={handleSkip}
          className="text-gray-500 hover:text-white text-sm transition-colors"
        >
          Passer l'introduction
        </button>
      </div>

      {/* Main content */}
      <div className="flex-1 flex items-center justify-center px-8">
        <div className="max-w-4xl w-full">
          <AnimatePresence mode="wait">
            <motion.div
              key={step.id}
              initial={{ opacity: 0, x: 50 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -50 }}
              transition={{ duration: 0.3 }}
              className="text-center"
            >
              {/* Icon */}
              <motion.div
                className={`w-24 h-24 mx-auto rounded-3xl bg-gradient-to-br ${step.color} 
                  flex items-center justify-center mb-8 shadow-2xl`}
                initial={{ scale: 0, rotate: -180 }}
                animate={{ scale: 1, rotate: 0 }}
                transition={{ type: 'spring', damping: 15 }}
              >
                <step.icon aria-hidden="true" className="w-12 h-12 text-white" />
              </motion.div>

              {/* Title */}
              <h1 className="text-4xl font-bold text-white mb-4">
                {step.title}
              </h1>

              {/* Description */}
              <p className="text-xl text-gray-400 mb-12 max-w-xl mx-auto">
                {step.description}
              </p>

              {/* Features */}
              <div className="grid grid-cols-3 gap-6 mb-12">
                {step.features.map((feature, i) => (
                  <motion.div
                    key={feature}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.1 }}
                    className="bg-white/5 rounded-xl p-5 border border-white/10"
                  >
                    <div aria-hidden="true" className={`w-10 h-10 rounded-lg bg-gradient-to-br ${step.color}
                      flex items-center justify-center mb-3 mx-auto opacity-70`}>
                      <Check className="w-5 h-5 text-white" />
                    </div>
                    <p className="text-gray-300 text-sm">{feature}</p>
                  </motion.div>
                ))}
              </div>

              {/* Step indicators */}
              <div className="flex justify-center gap-2 mb-12">
                {ONBOARDING_STEPS.map((s, i) => (
                  <button
                    key={s.id}
                    onClick={() => setCurrentStep(i)}
                    aria-label={`Aller à l’étape ${i + 1}`}
                    aria-current={i === currentStep ? 'step' : undefined}
                    className={`w-3 h-3 rounded-full transition-all ${
                      i === currentStep
                        ? 'bg-cyan-500 w-8'
                        : completedSteps.has(s.id)
                        ? 'bg-cyan-500/50'
                        : 'bg-gray-600'
                    }`}
                  />
                ))}
              </div>
            </motion.div>
          </AnimatePresence>
        </div>
      </div>

      {/* Navigation */}
      <div className="p-8 flex items-center justify-between max-w-4xl mx-auto w-full">
        <button
          onClick={handlePrev}
          disabled={isFirstStep}
          className={`flex items-center gap-2 px-6 py-3 rounded-xl transition-colors ${
            isFirstStep
              ? 'text-gray-600 cursor-not-allowed'
              : 'text-gray-400 hover:text-white hover:bg-white/5'
          }`}
        >
          <ChevronLeft aria-hidden="true" className="w-5 h-5" />
          Précédent
        </button>

        <button
          onClick={handleNext}
          className={`flex items-center gap-2 px-8 py-3 rounded-xl font-semibold transition-all
            bg-gradient-to-r ${step.color} text-white
            hover:shadow-lg hover:shadow-cyan-500/20 hover:scale-105`}
        >
          {isLastStep ? (
            <>
              Commencer
              <ArrowRight aria-hidden="true" className="w-5 h-5" />
            </>
          ) : (
            <>
              Suivant
              <ChevronRight aria-hidden="true" className="w-5 h-5" />
            </>
          )}
        </button>
      </div>
    </div>
  );
}

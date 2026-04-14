'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { motion } from 'framer-motion';
import {
  Play,
  FileText,
  Stethoscope,
  Heart,
  Pill,
  Activity,
  Syringe,
  ClipboardCheck,
  ArrowRight,
} from 'lucide-react';

const fullHeadline = 'Medical Documentation, Automated.';

const floatingIcons = [
  { icon: Stethoscope, x: '10%', y: '20%', delay: 0, size: 24 },
  { icon: Heart, x: '85%', y: '15%', delay: 0.5, size: 20 },
  { icon: Pill, x: '75%', y: '70%', delay: 1, size: 22 },
  { icon: Activity, x: '15%', y: '75%', delay: 1.5, size: 26 },
  { icon: Syringe, x: '90%', y: '45%', delay: 2, size: 18 },
  { icon: ClipboardCheck, x: '5%', y: '50%', delay: 0.8, size: 20 },
];

export default function Hero() {
  const [displayText, setDisplayText] = useState('');
  const [showCursor, setShowCursor] = useState(true);

  useEffect(() => {
    let index = 0;
    const interval = setInterval(() => {
      if (index <= fullHeadline.length) {
        setDisplayText(fullHeadline.slice(0, index));
        index++;
      } else {
        clearInterval(interval);
        setTimeout(() => setShowCursor(false), 2000);
      }
    }, 55);
    return () => clearInterval(interval);
  }, []);

  return (
    <section className="relative min-h-screen flex items-center justify-center pt-16 bg-[#0A192F]">
      {/* ====== AMBIENT GLOWS — dramatic visibility ====== */}
      {/* Left glow — blue */}
      <div className="absolute top-[5%] -left-[150px] w-[600px] h-[600px] rounded-full bg-blue-500 opacity-50 blur-[120px] pointer-events-none z-0" />
      {/* Right glow — teal */}
      <div className="absolute top-[10%] -right-[100px] w-[550px] h-[550px] rounded-full bg-teal-400 opacity-40 blur-[120px] pointer-events-none z-0" />
      {/* Center glow — purple */}
      <div className="absolute top-[30%] left-[20%] w-[700px] h-[700px] rounded-full bg-violet-600 opacity-25 blur-[140px] pointer-events-none z-0" />
      {/* Bottom-left accent */}
      <div className="absolute bottom-[10%] left-[5%] w-[400px] h-[400px] rounded-full bg-indigo-500 opacity-30 blur-[100px] pointer-events-none z-0" />
      {/* Bottom-right accent — cyan */}
      <div className="absolute bottom-[5%] right-[10%] w-[450px] h-[450px] rounded-full bg-cyan-400 opacity-30 blur-[100px] pointer-events-none z-0" />

      {/* Floating Medical Icons */}
      {floatingIcons.map((item, i) => {
        const Icon = item.icon;
        return (
          <motion.div
            key={i}
            className="absolute pointer-events-none z-[1]"
            style={{ left: item.x, top: item.y }}
            initial={{ opacity: 0, scale: 0 }}
            animate={{ opacity: 0.2, scale: 1 }}
            transition={{ delay: item.delay + 0.5, duration: 0.8 }}
          >
            <motion.div
              animate={{ y: [0, -15, 0], rotate: [0, 5, -5, 0] }}
              transition={{ duration: 5 + i, repeat: Infinity, ease: 'easeInOut' }}
            >
              <Icon className="text-blue-400/30" size={item.size} />
            </motion.div>
          </motion.div>
        );
      })}

      {/* ====== MAIN CONTENT ====== */}
      <div className="relative z-10 mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 w-full">
        <div className="grid lg:grid-cols-2 gap-12 items-center">
          {/* Left: Text Content */}
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8 }}
            className="text-center lg:text-left"
          >
            {/* Badge */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
              className="inline-flex items-center gap-2 rounded-full border border-blue-500/30 bg-blue-500/10 backdrop-blur-sm px-4 py-1.5 text-sm text-blue-300 mb-6"
            >
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400 opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-blue-500" />
              </span>
              Now with AI-Powered Assistant
            </motion.div>

            {/* Headline with typing effect */}
            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-bold tracking-tight text-white leading-tight">
              {displayText}
              {showCursor && (
                <span className="animate-typing-cursor inline-block w-[3px] h-[1em] bg-blue-500 ml-1 align-middle" />
              )}
            </h1>

            {/* Subtitle */}
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 2.5 }}
              className="mt-6 text-lg sm:text-xl text-slate-400 max-w-xl mx-auto lg:mx-0 leading-relaxed"
            >
              Generate professional procedure notes in seconds. AI-powered,
              accurate, and customizable.
            </motion.p>

            {/* CTA Buttons */}
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 2.8 }}
              className="mt-8 flex flex-col sm:flex-row items-center gap-4 justify-center lg:justify-start"
            >
              {/* Primary CTA with glow */}
              <Link
                href="/register"
                className="group relative inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-blue-600 to-teal-500 px-8 py-3.5 text-base font-semibold text-white transition-all duration-300 hover:scale-105 shadow-[0_0_25px_rgba(59,130,246,0.4)] hover:shadow-[0_0_40px_rgba(6,182,212,0.5)]"
              >
                Start Free Trial
                <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-1" />
              </Link>
              <button className="group inline-flex items-center gap-2 rounded-xl border border-slate-700 bg-slate-900/80 backdrop-blur-sm px-8 py-3.5 text-base font-semibold text-slate-300 transition-all duration-300 hover:border-blue-500/50 hover:text-white hover:shadow-[0_0_15px_rgba(59,130,246,0.15)]">
                <Play className="h-4 w-4" />
                Watch Demo
              </button>
            </motion.div>

            {/* Trust indicators */}
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 3.2 }}
              className="mt-10 flex items-center gap-6 justify-center lg:justify-start text-sm text-slate-400"
            >
              <span className="flex items-center gap-1.5">
                <svg className="h-4 w-4 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                </svg>
                Free 14-day trial
              </span>
              <span className="flex items-center gap-1.5">
                <svg className="h-4 w-4 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                </svg>
                No credit card needed
              </span>
              <span className="flex items-center gap-1.5">
                <svg className="h-4 w-4 text-green-500" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                </svg>
                HIPAA aware
              </span>
            </motion.div>
          </motion.div>

          {/* Right: Mockup Illustration */}
          <motion.div
            initial={{ opacity: 0, x: 40 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.5, duration: 0.8 }}
            className="relative hidden lg:block"
          >
            <div className="relative">
              {/* Glow behind mockup */}
              <div className="absolute inset-0 bg-gradient-to-r from-blue-500/20 to-teal-500/20 rounded-3xl blur-2xl scale-110" />

              {/* Document mockup card — glassmorphism */}
              <div className="relative rounded-2xl border border-white/10 bg-[#0A192F]/80 p-6 shadow-2xl backdrop-blur-md">
                {/* Mockup header */}
                <div className="flex items-center gap-2 mb-4">
                  <div className="h-3 w-3 rounded-full bg-red-400" />
                  <div className="h-3 w-3 rounded-full bg-yellow-400" />
                  <div className="h-3 w-3 rounded-full bg-green-400" />
                  <div className="ml-4 flex-1 h-6 rounded-md bg-white/5" />
                </div>

                {/* Mockup content - Document being generated */}
                <div className="space-y-4">
                  <div className="flex items-center gap-3 rounded-lg bg-blue-500/10 border border-blue-500/20 p-3">
                    <FileText className="h-5 w-5 text-blue-400 shrink-0" />
                    <div>
                      <p className="text-sm font-medium text-slate-200">LESI Procedure Note</p>
                      <p className="text-xs text-slate-400">Generating document...</p>
                    </div>
                    <motion.div
                      className="ml-auto"
                      animate={{ rotate: 360 }}
                      transition={{ duration: 2, repeat: Infinity, ease: 'linear' }}
                    >
                      <div className="h-5 w-5 rounded-full border-2 border-blue-800 border-t-blue-400" />
                    </motion.div>
                  </div>

                  {/* Animated text lines */}
                  {[0.85, 1, 0.7, 0.9, 0.6, 0.8, 0.75].map((width, i) => (
                    <motion.div
                      key={i}
                      className="h-3 rounded bg-white/5"
                      style={{ width: `${width * 100}%` }}
                      initial={{ opacity: 0, scaleX: 0 }}
                      animate={{ opacity: 1, scaleX: 1 }}
                      transition={{ delay: 1 + i * 0.15, duration: 0.4 }}
                    />
                  ))}

                  {/* Completion badge */}
                  <motion.div
                    initial={{ opacity: 0, scale: 0.8 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: 2.5 }}
                    className="flex items-center gap-2 rounded-lg bg-green-500/10 border border-green-500/20 p-3"
                  >
                    <svg className="h-5 w-5 text-green-400" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                    <p className="text-sm font-medium text-green-300">
                      Document ready for download
                    </p>
                  </motion.div>
                </div>
              </div>

              {/* Floating mini-cards — glassmorphism */}
              <motion.div
                className="absolute -top-4 -right-4 rounded-xl border border-white/10 bg-[#0A192F]/80 backdrop-blur-md p-3 shadow-lg shadow-teal-500/10"
                animate={{ y: [0, -8, 0] }}
                transition={{ duration: 3, repeat: Infinity, ease: 'easeInOut' }}
              >
                <div className="flex items-center gap-2">
                  <div className="h-8 w-8 rounded-lg bg-teal-500/15 flex items-center justify-center">
                    <Activity className="h-4 w-4 text-teal-400" />
                  </div>
                  <div>
                    <p className="text-xs font-medium text-slate-200">26+ Templates</p>
                    <p className="text-[10px] text-slate-400">All specialties</p>
                  </div>
                </div>
              </motion.div>

              <motion.div
                className="absolute -bottom-4 -left-4 rounded-xl border border-white/10 bg-[#0A192F]/80 backdrop-blur-md p-3 shadow-lg shadow-blue-500/10"
                animate={{ y: [0, -6, 0] }}
                transition={{ duration: 4, repeat: Infinity, ease: 'easeInOut', delay: 1 }}
              >
                <div className="flex items-center gap-2">
                  <div className="h-8 w-8 rounded-lg bg-blue-500/15 flex items-center justify-center">
                    <Stethoscope className="h-4 w-4 text-blue-400" />
                  </div>
                  <div>
                    <p className="text-xs font-medium text-slate-200">AI Assistant</p>
                    <p className="text-[10px] text-slate-400">Natural language</p>
                  </div>
                </div>
              </motion.div>
            </div>
          </motion.div>
        </div>
      </div>

      {/* Bottom gradient fade */}
      <div className="absolute bottom-0 left-0 right-0 h-32 bg-gradient-to-t from-slate-950 to-transparent" />
    </section>
  );
}

import { useState, useMemo } from 'react';
import { Gauge, Wallet } from 'lucide-react';
import type { PlanOption } from '../../Plan';
import type { SoloSingleTripData } from '../../../../context/TripContext';
import { SOLO_SINGLE_HUB_STEPS } from '../../Plan';

type SoloSingleStep5Props = {
  tripData: SoloSingleTripData | null;
  updateTripData: (patch: Partial<SoloSingleTripData>) => void;
  onNext: () => void;
};

const THEME = {
  iconBg: 'bg-cyan/10 border-cyan/15',
  iconColor: 'text-cyan',
  hoverTitle: 'group-hover:text-cyan',
  glowColor: 'rgba(102,252,241,0.20)',
};

// --- Choice Card (Big Screen) ---
type ChoiceCardProps = {
  choice: PlanOption;
  isSelected: boolean;
  onSelect: () => void;
  index: number;
};

function ChoiceCard({ choice, isSelected, onSelect, index }: ChoiceCardProps) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`group relative rounded-xl border p-4 text-left transition-all duration-300 cursor-pointer overflow-hidden ${
        isSelected
          ? 'border-cyan/40 bg-cyan/10 shadow-[0_0_24px_rgba(102,252,241,0.15)]'
          : 'border-white/[0.08] bg-white/[0.02] hover:border-cyan/25 hover:bg-cyan/5'
      }`}
      style={{ animation: `fade-in 400ms ease-out ${index * 60}ms both` }}
    >
      <div
        className="pointer-events-none absolute -inset-12 opacity-0 group-hover:opacity-100 transition-opacity duration-300 blur-2xl"
        style={{
          background: isSelected
            ? 'radial-gradient(circle at 50% 50%, rgba(102,252,241,0.18), transparent 60%)'
            : 'radial-gradient(circle at 50% 50%, rgba(102,252,241,0.08), transparent 60%)',
        }}
      />
      <div className="relative">
        <h3 className={`text-sm font-bold ${isSelected ? 'text-cyan' : 'text-white group-hover:text-cyan/90'}`}>
          {choice.title}
        </h3>
        <p className="mt-1 text-[11px] text-white/40 leading-relaxed">{choice.description}</p>
      </div>
    </button>
  );
}

// --- Slider Card (Small Screen) ---
type SliderCardProps = {
  title: string;
  subtitle: string;
  Icon: React.ElementType;
  choices: PlanOption[];
  value: string;
  onChange: (id: string) => void;
  gradientPos?: string;
};

function SliderCard({ title, subtitle, Icon, choices, value, onChange, gradientPos = '30% 20%' }: SliderCardProps) {
  const selectedIndex = choices.findIndex((c) => c.id === value);
  const displayIndex = selectedIndex >= 0 ? selectedIndex : 2;
  const currentChoice = choices[displayIndex] ?? choices[2];

  const handleSliderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const idx = Number(e.target.value);
    const choice = choices[idx];
    if (choice) onChange(choice.id);
  };

  return (
    <div className="group relative rounded-2xl border border-white/[0.08] bg-carbon/40 backdrop-blur-sm p-6 overflow-hidden">
      <div className="pointer-events-none absolute -inset-24 opacity-0 group-hover:opacity-100 transition-opacity duration-300 blur-3xl">
        <div
          className="absolute inset-0"
          style={{ background: `radial-gradient(circle at ${gradientPos}, ${THEME.glowColor}, transparent 58%)` }}
        />
      </div>

      <div className="relative flex items-center gap-3 mb-3">
        <div className={`h-11 w-11 rounded-xl flex items-center justify-center border ${THEME.iconBg}`}>
          <Icon size={18} className={THEME.iconColor} />
        </div>
        <div className="min-w-0">
          <h2 className={`text-lg font-bold text-white transition-colors ${THEME.hoverTitle}`}>{title}</h2>
          <p className="text-xs text-white/35">{subtitle}</p>
        </div>
      </div>

      <div className="relative mt-4 space-y-3">
        <input
          type="range"
          min={0}
          max={choices.length - 1}
          value={displayIndex}
          onChange={handleSliderChange}
          className="w-full h-2 rounded-full appearance-none bg-white/10 accent-cyan cursor-pointer"
          style={{
            background: `linear-gradient(to right, rgba(102,252,241,0.5) 0%, rgba(102,252,241,0.5) ${(displayIndex / (choices.length - 1)) * 100}%, rgba(255,255,255,0.1) ${(displayIndex / (choices.length - 1)) * 100}%, rgba(255,255,255,0.1) 100%)`,
          }}
        />
        <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-3">
          <h3 className="text-sm font-bold text-cyan">{currentChoice.title}</h3>
          <p className="mt-1 text-[11px] text-white/40 leading-relaxed">{currentChoice.description}</p>
        </div>
      </div>
    </div>
  );
}

// --- Main Section Card (Big Screen) ---
type SectionCardProps = {
  title: string;
  subtitle: string;
  Icon: React.ElementType;
  choices: PlanOption[];
  value: string;
  onChange: (id: string) => void;
  gradientPos?: string;
};

function SectionCard({ title, subtitle, Icon, choices, value, onChange, gradientPos = '30% 20%' }: SectionCardProps) {
  return (
    <div className="group relative rounded-2xl border border-white/[0.08] bg-carbon/40 backdrop-blur-sm p-8 overflow-hidden">
      <div className="pointer-events-none absolute -inset-24 opacity-0 group-hover:opacity-100 transition-opacity duration-300 blur-3xl">
        <div
          className="absolute inset-0"
          style={{ background: `radial-gradient(circle at ${gradientPos}, ${THEME.glowColor}, transparent 58%)` }}
        />
      </div>

      <div className="relative flex items-center gap-3 mb-6">
        <div className={`h-11 w-11 rounded-xl flex items-center justify-center border ${THEME.iconBg}`}>
          <Icon size={18} className={THEME.iconColor} />
        </div>
        <div className="min-w-0">
          <h2 className={`text-lg font-bold text-white transition-colors ${THEME.hoverTitle}`}>{title}</h2>
          <p className="text-xs text-white/35">{subtitle}</p>
        </div>
      </div>

      <div className="relative grid grid-cols-1 sm:grid-cols-5 gap-3">
        {choices.map((choice, i) => (
          <ChoiceCard
            key={choice.id}
            choice={choice}
            isSelected={value === choice.id}
            onSelect={() => onChange(choice.id)}
            index={i}
          />
        ))}
      </div>
    </div>
  );
}

export function SoloSingleStep5BudgetPacing({ tripData, updateTripData, onNext }: SoloSingleStep5Props) {
  const stepMeta = useMemo(
    () => SOLO_SINGLE_HUB_STEPS.find((s) => s.id === 'budget-pacing'),
    [],
  );

  const paceOption = useMemo(() => stepMeta?.options?.find((o) => o.id === 'pace'), [stepMeta]);
  const budgetOption = useMemo(() => stepMeta?.options?.find((o) => o.id === 'budget'), [stepMeta]);

  const paceChoices = paceOption?.choices ?? [];
  const budgetChoices = budgetOption?.choices ?? [];

  const [pace, setPace] = useState<string | null>(tripData?.pace ?? null);
  const [budget, setBudget] = useState<string | null>(tripData?.budget ?? null);

  const paceChoice = paceChoices.find((c) => c.id === pace) ?? paceChoices[2];
  const budgetChoice = budgetChoices.find((c) => c.id === budget) ?? budgetChoices[2];

  const canConfirm = pace !== null && budget !== null;

  const handleConfirm = () => {

    updateTripData({ pace, budget });
    onNext();
  };

  return (
    <>
    <div className={`w-full max-w-5xl animate-[fade-in_400ms_ease-out] ${canConfirm ? 'pb-24' : ''}`}>
      {/* Pace & Budget Cards - Big Screen: 5 subcards each */}
      <div className="space-y-6 hidden md:block">
        <SectionCard
          title={paceOption?.title ?? 'Trip Pace'}
          subtitle={paceOption?.description ?? 'Choose your pace'}
          Icon={Gauge}
          choices={paceChoices}
          value={pace ?? ''}
          onChange={setPace}
          gradientPos="20% 30%"
        />
        <SectionCard
          title={budgetOption?.title ?? 'Trip Budget'}
          subtitle={budgetOption?.description ?? 'Choose your budget'}
          Icon={Wallet}
          choices={budgetChoices}
          value={budget ?? ''}
          onChange={setBudget}
          gradientPos="70% 20%"
        />
      </div>

      {/* Small Screen: Slider 1-5 with current title/description */}
      <div className="space-y-6 md:hidden">
        <SliderCard
          title={paceOption?.title ?? 'Trip Pace'}
          subtitle={paceOption?.description ?? 'Choose your pace'}
          Icon={Gauge}
          choices={paceChoices}
          value={pace ?? ''}
          onChange={setPace}
          gradientPos="20% 30%"
        />
        <SliderCard
          title={budgetOption?.title ?? 'Trip Budget'}
          subtitle={budgetOption?.description ?? 'Choose your budget'}
          Icon={Wallet}
          choices={budgetChoices}
          value={budget ?? ''}
          onChange={setBudget}
          gradientPos="70% 20%"
        />
      </div>     
      </div> 

      {/* Sticky Yes button at bottom of viewport */}
      {canConfirm && (
        <div className="fixed bottom-0 left-0 w-full z-50 pointer-events-none flex justify-center pb-8 pt-32 bg-gradient-to-t from-black via-black/80 to-transparent">
          <div className="pointer-events-auto">
            <div className="flex items-center gap-4 rounded-full px-6 py-3">
            <span className="text-sm text-white/70 text-center">
                Do you want {/^[aeiou]/i.test(paceChoice?.title ?? '') ? 'an' : 'a'}{' '}
                <span className="text-cyan font-semibold">{paceChoice?.title ?? 'Balanced'}</span>{' '}
                trip on a{' '}
                <span className="text-cyan font-semibold">{budgetChoice?.title ?? 'Comfortable'}</span> budget?
              </span>
              <button
                type="button"
                onClick={handleConfirm}
                className="ml-2 inline-flex items-center justify-center rounded-full bg-cyan text-midnight font-extrabold text-xs px-4 py-2 transition-transform duration-300 hover:scale-105 hover:bg-[#80fdf6] hover:shadow-[0_0_15px_rgba(102,252,241,0.4)] cursor-pointer"
              >
                YES
              </button>
            </div>
          </div>
        </div>
      )}
      {canConfirm && <div className="h-16 shrink-0" aria-hidden />}
    </>
  );
}

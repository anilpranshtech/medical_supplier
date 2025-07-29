document.addEventListener('DOMContentLoaded', function () {
    const monthlyPlanBtn = document.getElementById('monthlyPlan');
    const annuallyPlanBtn = document.getElementById('annuallyPlan');
    const monthlyPlans = document.querySelectorAll('.monthly-plan');
    const annuallyPlans = document.querySelectorAll('.annually-plan');
    const packageModal = document.getElementById('package_modal');
    const confirmCheckbox = document.getElementById('subscription_package_confirm');
    const confirmBtn = document.getElementById('btn_subscription_package_confirm');
    const cancelBtn = document.getElementById('btn_subscription_package_cancelled');
    const packageModalPlanId = document.getElementById('package_modal_plan_id');
    const confirmError = document.getElementById('subscription_package_confirm_required');

    // Toggle Monthly Plans
    monthlyPlanBtn.addEventListener('click', function () {
        monthlyPlanBtn.classList.add('bg-white', 'dark:bg-gray-600', 'active');
        annuallyPlanBtn.classList.remove('bg-white', 'dark:bg-gray-600', 'active');
        monthlyPlans.forEach(plan => plan.classList.remove('hidden'));
        annuallyPlans.forEach(plan => plan.classList.add('hidden'));
    });

    // Toggle Annual Plans
    annuallyPlanBtn.addEventListener('click', function () {
        annuallyPlanBtn.classList.add('bg-white', 'dark:bg-gray-600', 'active');
        monthlyPlanBtn.classList.remove('bg-white', 'dark:bg-gray-600', 'active');
        annuallyPlans.forEach(plan => plan.classList.remove('hidden'));
        monthlyPlans.forEach(plan => plan.classList.add('hidden'));
    });

    // Open Modal
    document.querySelectorAll('.btnPackage').forEach(button => {
        button.addEventListener('click', function () {
            const planId = this.getAttribute('data-plan-id');
            packageModalPlanId.value = planId;
            packageModal.classList.remove('hidden');
        });
    });

    // Cancel Modal
    cancelBtn.addEventListener('click', function () {
        packageModal.classList.add('hidden');
        confirmCheckbox.checked = false;
        confirmError.classList.add('hidden');
    });

    // Confirm Modal
    confirmBtn.addEventListener('click', function () {
        if (!confirmCheckbox.checked) {
            confirmError.classList.remove('hidden');
            return;
        }

        const planId = packageModalPlanId.value;
        confirmBtn.querySelector('.indicator-label').classList.add('hidden');
        confirmBtn.querySelector('.indicator-progress').classList.remove('hidden');

        // Simulated API call
        setTimeout(() => {
            packageModal.classList.add('hidden');
            confirmCheckbox.checked = false;
            confirmBtn.querySelector('.indicator-label').classList.remove('hidden');
            confirmBtn.querySelector('.indicator-progress').classList.add('hidden');
        }, 1000);
    });

    confirmCheckbox.addEventListener('change', function () {
        if (this.checked) {
            confirmError.classList.add('hidden');
        }
    });
});

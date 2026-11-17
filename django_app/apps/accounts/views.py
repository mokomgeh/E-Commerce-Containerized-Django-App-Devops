"""
apps.accounts.views
=====================
Signup + address book CRUD. Login/logout use Django's built-in
auth views (wired up in config/urls.py) rather than reinventing them --
they already handle CSRF, throttling hooks, and "next" redirects correctly.
"""
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from .forms import AddressForm, SignUpForm
from .models import Address


class SignUpView(CreateView):
    form_class = SignUpForm
    template_name = "accounts/signup.html"
    success_url = "/"

    def form_valid(self, form):
        response = super().form_valid(form)
        # Log the user in immediately after registering -- a small UX win
        # that avoids forcing a second round trip through the login form.
        login(self.request, self.object)
        messages.success(self.request, "Welcome! Your account has been created.")
        return response


@login_required
def address_list(request):
    addresses = request.user.addresses.all()
    return render(request, "accounts/address_list.html", {"addresses": addresses})


@login_required
def address_create(request):
    if request.method == "POST":
        form = AddressForm(request.POST)
        if form.is_valid():
            address = form.save(commit=False)
            address.user = request.user
            address.save()
            messages.success(request, "Address saved.")
            return redirect("accounts:address_list")
    else:
        form = AddressForm()
    return render(request, "accounts/address_form.html", {"form": form})


@login_required
def address_update(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)
    if request.method == "POST":
        form = AddressForm(request.POST, instance=address)
        if form.is_valid():
            form.save()
            messages.success(request, "Address updated.")
            return redirect("accounts:address_list")
    else:
        form = AddressForm(instance=address)
    return render(request, "accounts/address_form.html", {"form": form, "address": address})


@login_required
def address_delete(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)
    if request.method == "POST":
        address.delete()
        messages.success(request, "Address removed.")
        return redirect("accounts:address_list")
    return render(request, "accounts/address_confirm_delete.html", {"address": address})

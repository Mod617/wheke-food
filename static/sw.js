self.addEventListener("push", function(event){

self.registration.showNotification("Nouvelle commande",{
body:"Un client vient de commander"
})

})